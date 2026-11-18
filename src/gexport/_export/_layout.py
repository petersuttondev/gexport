from dataclasses import dataclass
from typing import Final, NamedTuple, Self, final


@final
class Region(NamedTuple):
    x: int
    y: int
    w: int
    h: int

    @property
    def top(self) -> int:
        return self.y

    @property
    def left(self) -> int:
        return self.x

    @property
    def bottom(self) -> int:
        return self.top + self.h

    @property
    def right(self) -> int:
        return self.left + self.w

    def intersect(self, other: Self) -> Self:
        top = max(self.top, other.top)
        bottom = min(self.bottom, other.bottom)
        left = max(self.left, other.left)
        right = min(self.right, other.right)
        if bottom <= top or right <= left:
            raise ValueError("Regions do not intersect")
        return type(self)(left, top, right - left, bottom - top)


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class Layout:
    width: Final[int]
    height: Final[int]
    x_offset: Final[int]
    y_offset: Final[int]
    x_scale: Final[float]
    y_scale: Final[float]


@final
class Point(NamedTuple):
    x: int
    y: int

    def add(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)


@final
class Span(NamedTuple):
    length: int
    offset: int
