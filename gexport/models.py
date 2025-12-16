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
    group: str
    default: Action | None = None
    show: 'list[Group | Layer | str] | Group | Layer | str | None' = None
    hide: 'list[Group | Layer | str] | Group | Layer | str | None' = None
    leave: 'list[Group | Layer | str] | Group | Layer | str | None' = None
    model_config = ConfigDict(extra='forbid')


@final
class CropAlgorithem(BaseModel):
    algorithm: Literal['bounding-box']
    model_config = ConfigDict(extra='forbid')


@final
class WidthHeight(BaseModel):
    width: int | None = None
    height: int | None = None
    model_config = ConfigDict(extra='forbid')


@final
class Export(BaseModel):
    default: Action | None = None
    crop: CropAlgorithem | str | None = None
    resize: WidthHeight | float | None = None
    show: list[Group | Layer | str] | Group | Layer | str | None = None
    hide: list[Group | Layer | str] | Group | Layer | str | None = None
    leave: list[Group | Layer | str] | Group | Layer | str | None = None
    model_config = ConfigDict(extra='forbid')


@final
class XCF(BaseModel):
    default: Action | None = None
    exports: dict[Path, Export] | None = None
    resize: WidthHeight | float | None = None
    model_config = ConfigDict(extra='forbid')


@final
class Schema(BaseModel):
    database: Path
    resize: WidthHeight | float | None = None
    xcfs: dict[Path, XCF] | None = None
    model_config = ConfigDict(extra='forbid')


def load_schema(path: Path) -> Schema:
    with open(path) as schema_file:
        return Schema(**yaml.safe_load(schema_file))
