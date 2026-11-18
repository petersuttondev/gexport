import os
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Final, final

from pydantic.config import ConfigDict
from pydantic.fields import Field
from pydantic.main import BaseModel

from gexport._util import StrPathLike

_KEY: Final = "GEXPORT_EXPORT"


def _make_response_path(working_dir: StrPathLike) -> Path:
    return Path(working_dir, "export-response.json")


@final
class ExportRequest(BaseModel, frozen=True):  # pyright: ignore[reportUninitializedInstanceVariable]
    model_config = ConfigDict(extra="forbid")
    manifest_path: Final[Path]
    working_dir: Final[Path]
    substrings: Annotated[Final[list[str]], Field(default_factory=list)]


def load_export_request() -> ExportRequest:
    return ExportRequest.model_validate_json(os.environ[_KEY])


def make_export_request(
    manifest_path: StrPathLike,
    working_dir: StrPathLike,
    substrings: Iterable[str] | None = None,
) -> dict[str, str]:
    if substrings is None:
        substrings = []
    else:
        substrings = list(substrings)
    return {
        _KEY: ExportRequest(
            manifest_path=Path(manifest_path),
            working_dir=Path(working_dir),
            substrings=substrings,
        ).model_dump_json()
    }


@final
class ExportResponse(BaseModel, frozen=True):  # pyright: ignore[reportUninitializedInstanceVariable]
    model_config = ConfigDict(extra="forbid")
    export_paths: Final[list[Path]]


def read_export_response(working_dir: StrPathLike) -> ExportResponse:
    return ExportResponse.model_validate_json(
        _make_response_path(working_dir).read_bytes()
    )


def write_export_response(
    export_paths: Iterable[StrPathLike],
    working_dir: StrPathLike,
) -> None:
    export_paths = [Path(export_path) for export_path in export_paths]
    with open(_make_response_path(working_dir), "w") as response_file:
        response_file.write(
            ExportResponse(export_paths=export_paths).model_dump_json(),
        )
