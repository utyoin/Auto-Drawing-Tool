from __future__ import annotations

import math

from mouse_draw_app.models import Bounds, DrawRegion, OutlineDocument, PathStroke, Point, compute_bounds


class PathTransformService:
    def fit_outline_to_region(
        self,
        document: OutlineDocument,
        region: DrawRegion,
        simplify_tolerance: float = 0.0,
    ) -> list[PathStroke]:
        if document.is_empty():
            return []
        bounds = document.bounds
        if bounds.width <= 0 or bounds.height <= 0:
            return []

        scale = min(region.width / bounds.width, region.height / bounds.height)
        offset_x = region.left + (region.width - bounds.width * scale) / 2.0
        offset_y = region.top + (region.height - bounds.height * scale) / 2.0

        transformed: list[PathStroke] = []
        for stroke in document.paths:
            new_points = [
                Point(
                    x=offset_x + (point.x - bounds.left) * scale,
                    y=offset_y + (point.y - bounds.top) * scale,
                )
                for point in stroke.points
            ]
            simplified = self._simplify_points(new_points, simplify_tolerance)
            if len(simplified) >= 2:
                transformed.append(PathStroke(points=simplified, closed=stroke.closed))
        return transformed

    def bounds_for_paths(self, paths: list[PathStroke]) -> Bounds:
        return compute_bounds(paths)

    def _simplify_points(self, points: list[Point], tolerance: float) -> list[Point]:
        if tolerance <= 0 or len(points) <= 2:
            return points

        simplified = [points[0]]
        for point in points[1:-1]:
            last = simplified[-1]
            if math.dist((last.x, last.y), (point.x, point.y)) >= tolerance:
                simplified.append(point)
        simplified.append(points[-1])
        return simplified
