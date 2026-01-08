from enum import Enum, unique
from pathlib import Path
from typing import Literal, final

from pydantic import BaseModel, ConfigDict
import yaml


@final
@unique
class Action(Enum):
    SHOW = 'show'
    HIDE = 'hide'
    LEAVE = 'leave'


@final
class Layer(BaseModel):
    layer: str
    mask: Action | None = None
    model_config = ConfigDict(extra='forbid')


@final
class Group(BaseModel):
    model_config = ConfigDict(extra='forbid')

    group: str
    default: Action | None = None
    show: 'list[Group | Layer | str] | Group | Layer | str | None' = None
    hide: 'list[Group | Layer | str] | Group | Layer | str | None' = None
    leave: 'list[Group | Layer | str] | Group | Layer | str | None' = None


@final
class CropAlgorithm(BaseModel):
    model_config = ConfigDict(extra='forbid')

    algorithm: Literal['bounding-box']


@final
class WidthHeight(BaseModel):
    model_config = ConfigDict(extra='forbid')

    width: int | None = None
    height: int | None = None


@final
class Export(BaseModel):
    model_config = ConfigDict(extra='forbid')

    default: Action | None = None
    crop: CropAlgorithm | str | None = None
    resize: WidthHeight | float | None = None
    show: list[Group | Layer | str] | Group | Layer | str | None = None
    hide: list[Group | Layer | str] | Group | Layer | str | None = None
    leave: list[Group | Layer | str] | Group | Layer | str | None = None


@final
class XCF(BaseModel):
    model_config = ConfigDict(extra='forbid')

    default: Action | None = None
    exports: dict[Path, Export] | list[Path] | Path | None = None
    resize: WidthHeight | float | None = None


@final
class Schema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    database: Path
    crop: CropAlgorithm | str | None = None
    resize: WidthHeight | float | None = None
    xcfs: dict[Path, XCF] | None = None


def load_schema(path: Path) -> Schema:
    with open(path) as schema_file:
        return Schema(**yaml.safe_load(schema_file))
