from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from mouse_draw_app.models import OutlineDocument, PathStroke, Point, compute_bounds


class ImageOutlineError(ValueError):
    """图片无法转换为线稿路径时抛出。"""


class ImageOutlineService:
    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

    def generate_outline_from_image(self, image_path: str | Path, detail_level: int) -> OutlineDocument:
        path = Path(image_path)
        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ImageOutlineError(f"不支持的图片格式：{path.suffix}")

        buffer = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ImageOutlineError("图片加载失败。")

        detail_level = max(1, min(detail_level, 100))
        processed, scale = self._prepare_image(image)
        edge_mask = self._build_detail_edge_mask(processed, detail_level)
        paths = self._extract_dense_paths(edge_mask, detail_level, scale)

        if not paths:
            raise ImageOutlineError("未在图片中检测到可绘制的线稿。")

        bounds = compute_bounds(paths)
        return OutlineDocument(
            source_type="image",
            paths=paths,
            bounds=bounds,
            metadata={"detail_level": detail_level, "image_path": str(path)},
        )

    def _prepare_image(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        height, width = image.shape[:2]
        longest_side = max(height, width)

        scale = 1.0
        target_min_side = 640
        target_max_side = 1200

        if longest_side < target_min_side:
            scale = longest_side / target_min_side
            resized_width = max(1, int(round(width / scale)))
            resized_height = max(1, int(round(height / scale)))
            image = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_CUBIC)
        elif longest_side > target_max_side:
            scale = longest_side / target_max_side
            resized_width = max(1, int(round(width / scale)))
            resized_height = max(1, int(round(height / scale)))
            image = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)

        return image, scale

    def _build_detail_edge_mask(self, image: np.ndarray, detail_level: int) -> np.ndarray:
        denoised = cv2.bilateralFilter(image, d=7, sigmaColor=50, sigmaSpace=50)
        gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        median = float(np.median(gray))
        spread = 10 + detail_level * 0.35
        low_threshold = int(max(5, median - spread))
        high_threshold = int(min(255, median + spread))
        canny = cv2.Canny(gray, low_threshold, high_threshold, L2gradient=True)

        adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            7,
            2,
        )

        gradient_x = cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_16S, 0, 1, ksize=3)
        abs_x = cv2.convertScaleAbs(gradient_x)
        abs_y = cv2.convertScaleAbs(gradient_y)
        gradient = cv2.addWeighted(abs_x, 0.5, abs_y, 0.5, 0)
        _, gradient = cv2.threshold(gradient, max(12, 30 - detail_level // 8), 255, cv2.THRESH_BINARY)

        edge_mask = cv2.bitwise_or(canny, gradient)
        edge_mask = cv2.bitwise_or(edge_mask, adaptive if detail_level >= 70 else cv2.bitwise_and(adaptive, canny))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        edge_mask = cv2.morphologyEx(edge_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return self._remove_small_components(edge_mask, detail_level)

    def _remove_small_components(self, edge_mask: np.ndarray, detail_level: int) -> np.ndarray:
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(edge_mask, connectivity=8)
        cleaned = np.zeros_like(edge_mask)
        min_pixels = max(4, int((101 - detail_level) * 0.35))

        for component_index in range(1, component_count):
            area = stats[component_index, cv2.CC_STAT_AREA]
            if area >= min_pixels:
                cleaned[labels == component_index] = 255
        return cleaned

    def _extract_dense_paths(self, edge_mask: np.ndarray, detail_level: int, scale: float) -> list[PathStroke]:
        contours, _ = cv2.findContours(edge_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        image_area = edge_mask.shape[0] * edge_mask.shape[1]
        min_area = max(1.0, image_area * 0.000005)
        min_perimeter = max(6.0, 12.0 - detail_level * 0.04)
        epsilon = max(0.25, 1.1 - detail_level * 0.007)
        max_paths = int(180 + detail_level * 3.5)

        candidates: list[tuple[float, PathStroke]] = []
        for contour in contours:
            if len(contour) < 2:
                continue

            area = abs(cv2.contourArea(contour))
            perimeter = cv2.arcLength(contour, True)
            if area < min_area and perimeter < min_perimeter:
                continue

            approx = cv2.approxPolyDP(contour, epsilon, True)
            points = [Point(float(point[0][0] * scale), float(point[0][1] * scale)) for point in approx]
            if len(points) < 2:
                continue

            score = perimeter + area * 0.01
            candidates.append((score, PathStroke(points=points, closed=True)))

        candidates.sort(key=lambda item: item[0], reverse=True)
        selected = [stroke for _, stroke in candidates[:max_paths]]
        return selected
