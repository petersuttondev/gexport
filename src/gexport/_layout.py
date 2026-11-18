from collections.abc import Callable, Iterable
from pathlib import Path

from rich.console import Console
from rich.table import Column, Table

from gexport import models
from gexport.cli import LayoutArgs
from gexport.databaselib import Export, open_database


def _get_database_path(args: LayoutArgs) -> Path:
    if args.database_path is not None:
        return args.database_path
    manifest_path = args.manifest_path.resolve(strict=True)
    manifest = models.load_manifest(manifest_path)
    return manifest_path.parent / manifest.database


def _fetch_exports(
    database_path: Path, *, remove_layouts_without_files: bool = False
) -> list[Export]:
    with open_database(database_path) as db:
        if remove_layouts_without_files:
            db.remove_data_for_missing_files()
        return list(db.iter_exports())


def _create_table(exports: Iterable[Export]) -> Table:
    table = Table(
        Column("Name", justify="right"),
        Column("W", justify="right"),
        Column("H", justify="right"),
        Column("X←", justify="right"),
        Column("Y↑", justify="right"),
        Column("X→", justify="right"),
        Column("Y↓", justify="right"),
        "X",
        "Y",
        title="Exports",
    )

    for (
        path,
        width,
        height,
        x_offset,
        y_offset,
        x_scale,
        y_scale,
    ) in exports:
        table.add_row(
            str(path.name),
            str(width),
            str(height),
            str(x_offset),
            str(y_offset),
            str(x_offset + width),
            str(y_offset + height),
            str(x_scale),
            str(y_scale),
        )

    return table


def print_layout_table(
    database_path: Path,
    *,
    include_export: Callable[[Export], bool] | None = None,
    remove_layouts_without_files: bool = False,
) -> None:
    if include_export is None:
        include_export = lambda _: True
    exports = [
        export
        for export in _fetch_exports(
            database_path,
            remove_layouts_without_files=remove_layouts_without_files,
        )
        if include_export(export)
    ]
    Console().print(_create_table(exports))


def layout_subcommand(args: LayoutArgs) -> None:
    print_layout_table(
        _get_database_path(args),
        include_export=(
            (
                lambda export: any(
                    substring in export.path.stem
                    for substring in args.substrings
                )
            )
            if args.substrings
            else None
        ),
        remove_layouts_without_files=args.clean,
    )
