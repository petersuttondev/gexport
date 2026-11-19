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
    SHOW = "show"
    HIDE = "hide"
    LEAVE = "leave"


@final
class Layer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layer: str
    mask: Action | SkipJsonSchema[None] = None


type VisibilityField = (
    list[Group | Layer | str] | Group | Layer | str | SkipJsonSchema[None]
)


@final
class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group: str
    default: Action | SkipJsonSchema[None] = None
    show: VisibilityField = None
    hide: VisibilityField = None
    leave: VisibilityField = None


type Crop = Literal["<content>", "<layers>"] | str

type CropField = list[Crop] | Crop | SkipJsonSchema[None]


@final
class ScaleFrom(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scale_from: str


@final
class WidthHeight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: int | SkipJsonSchema[None] = None
    height: int | SkipJsonSchema[None] = None
    allow_scale_up: bool | SkipJsonSchema[None] = None


type ResizeField = ScaleFrom | WidthHeight | float | SkipJsonSchema[None]


@final
class Export(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | SkipJsonSchema[None] = None
    origin: str | SkipJsonSchema[None] = None
    crop: CropField = None
    resize: ResizeField = None
    default: Action | SkipJsonSchema[None] = None
    show: VisibilityField = None
    hide: VisibilityField = None
    leave: VisibilityField = None


@final
class XCF(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resize: ResizeField = None
    default: Action | SkipJsonSchema[None] = None
    exports: (
        dict[Path, Export | None] | list[Path] | Path | SkipJsonSchema[None]
    ) = None


@final
class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database: Path
    crop: CropField = None
    resize: ResizeField = None
    xcfs: dict[Path, XCF] | SkipJsonSchema[None] = None


def load_manifest(path: Path) -> Manifest:
    with open(path) as manifest_file:
        return Manifest.model_validate(yaml.safe_load(manifest_file))
