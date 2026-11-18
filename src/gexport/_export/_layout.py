from dataclasses import dataclass
from typing import Final, NamedTuple, final


@final
class BoundingBox(NamedTuple):
    width: int
    height: int
    x_offset: int
    y_offset: int


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
class Offsets(NamedTuple):
    x: int
    y: int


@final
class Span(NamedTuple):
    length: int
    offset: int
