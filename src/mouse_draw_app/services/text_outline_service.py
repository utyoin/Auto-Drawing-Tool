from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath

from mouse_draw_app.models import OutlineDocument, PathStroke, Point, compute_bounds


class TextOutlineError(ValueError):
    """文字无法转换为线稿路径时抛出。"""


class TextOutlineService:
    def generate_outline_from_text(
        self,
        text: str,
        font_family: str,
        font_size: int = 160,
    ) -> OutlineDocument:
        cleaned = text.strip()
        if not cleaned:
            raise TextOutlineError("请先输入文字内容。")

        font = QFont(font_family, pointSize=font_size)
        font.setStyleStrategy(QFont.PreferAntialias)

        metrics = QFontMetricsF(font)
        baseline = metrics.ascent()
        painter_path = QPainterPath()
        painter_path.addText(QPointF(0.0, baseline), font, cleaned)

        polygons = painter_path.toSubpathPolygons()
        paths: list[PathStroke] = []
        for polygon in polygons:
            points = [Point(point.x(), point.y()) for point in polygon]
            if len(points) < 2:
                continue
            paths.append(PathStroke(points=points, closed=True))

        if not paths:
            raise TextOutlineError("当前所选字体未能生成可绘制的线稿。")

        bounds = compute_bounds(paths)
        return OutlineDocument(
            source_type="text",
            paths=paths,
            bounds=bounds,
            metadata={"text": cleaned, "font_family": font_family, "font_size": font_size},
        )
