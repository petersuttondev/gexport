# pyright: reportUninitializedInstanceVariable=false
from enum import Enum, unique
from pathlib import Path
from typing import Literal, final

import yaml
from pydantic.config import ConfigDict
from pydantic.json_schema import SkipJsonSchema
from pydantic.main import BaseModel


@final
@unique
class Action(Enum):
    SHOW = 'show'
    HIDE = 'hide'
    LEAVE = 'leave'


@final
class Layer(BaseModel):
    model_config = ConfigDict(extra='forbid')

    layer: str
    mask: Action | SkipJsonSchema[None] = None


@final
class Group(BaseModel):
    model_config = ConfigDict(extra='forbid')

    group: str
    default: Action | SkipJsonSchema[None] = None
    show: 'list[Group | Layer | str] | Group | Layer | str | None' = None
    hide: 'list[Group | Layer | str] | Group | Layer | str | None' = None
    leave: 'list[Group | Layer | str] | Group | Layer | str | None' = None


@final
class CropAlgorithm(BaseModel):
    model_config = ConfigDict(extra='forbid')

    algorithm: Literal['bounding-box']


@final
class ScaleFrom(BaseModel):
    model_config = ConfigDict(extra='forbid')

    scale_from: str


@final
class WidthHeight(BaseModel):
    model_config = ConfigDict(extra='forbid')

    width: int | SkipJsonSchema[None] = None
    height: int | SkipJsonSchema[None] = None
    allow_scale_up: bool | SkipJsonSchema[None] = None


@final
class Export(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str | SkipJsonSchema[None] = None
    default: Action | SkipJsonSchema[None] = None
    crop: CropAlgorithm | str | SkipJsonSchema[None] = None
    resize: ScaleFrom | WidthHeight | float | SkipJsonSchema[None] = None
    show: (
        list[Group | Layer | str] | Group | Layer | str | SkipJsonSchema[None]
    ) = None
    hide: (
        list[Group | Layer | str] | Group | Layer | str | SkipJsonSchema[None]
    ) = None
    leave: (
        list[Group | Layer | str] | Group | Layer | str | SkipJsonSchema[None]
    ) = None


@final
class XCF(BaseModel):
    model_config = ConfigDict(extra='forbid')

    default: Action | SkipJsonSchema[None] = None
    exports: dict[Path, Export] | list[Path] | Path | SkipJsonSchema[None] = (
        None
    )
    resize: ScaleFrom | WidthHeight | float | SkipJsonSchema[None] = None


@final
class Schema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    database: Path
    crop: CropAlgorithm | str | SkipJsonSchema[None] = None
    resize: ScaleFrom | WidthHeight | float | SkipJsonSchema[None] = None
    xcfs: dict[Path, XCF] | SkipJsonSchema[None] = None


def load_schema(path: Path) -> Schema:
    with open(path) as schema_file:
        return Schema(**yaml.safe_load(schema_file))  # pyright: ignore[reportAny]
