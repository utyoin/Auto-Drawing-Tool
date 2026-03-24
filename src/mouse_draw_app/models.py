from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass
class PathStroke:
    points: list[Point]
    closed: bool = False

    def is_empty(self) -> bool:
        return len(self.points) == 0


@dataclass(frozen=True)
class Bounds:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


@dataclass(frozen=True)
class DrawRegion:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass
class OutlineDocument:
    source_type: str
    paths: list[PathStroke]
    bounds: Bounds
    preview_image: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return len(self.paths) == 0


@dataclass
class DrawConfig:
    mouse_button: str = "left"
    move_speed: int = 30
    countdown_seconds: int = 3
    simplify_tolerance: float = 1.5
    region_fit_mode: str = "contain"


def compute_bounds(paths: list[PathStroke]) -> Bounds:
    all_points = [point for stroke in paths for point in stroke.points]
    if not all_points:
        return Bounds(0.0, 0.0, 0.0, 0.0)
    min_x = min(point.x for point in all_points)
    min_y = min(point.y for point in all_points)
    max_x = max(point.x for point in all_points)
    max_y = max(point.y for point in all_points)
    return Bounds(min_x, min_y, max_x - min_x, max_y - min_y)
