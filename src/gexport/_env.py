from pathlib import Path
from typing import Annotated, Final, final

from pydantic.config import ConfigDict
from pydantic.fields import Field
from pydantic.main import BaseModel


@final
class GexportEnv(BaseModel, frozen=True):  # pyright: ignore[reportUninitializedInstanceVariable]
    model_config = ConfigDict(extra="forbid")
    manifest: Final[Path]
    substrings: Annotated[Final[list[str]], Field(default_factory=list)]
