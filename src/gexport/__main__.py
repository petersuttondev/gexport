import json
import sys

from gexport import models
from gexport._gimp import GIMP
from gexport.cli import ExportArgs, JSONSchemaArgs, MetadataArgs, parse_args
from gexport.databaselib import open_database
from gexport.util import suppress_unhandled


def _export_subcommand(args: ExportArgs) -> None:
    gimp = GIMP(schema_path=args.schema_path, substrings=args.substrings)
    print(gimp.make_shell_command())
    gimp.exec()


def _json_schema_subcommand() -> None:
    json.dump(models.Schema.model_json_schema(), sys.stdout, indent=2)


def _metadata_subcommand(args: MetadataArgs) -> None:
    from rich.console import Console
    from rich.table import Column, Table

    if args.database_path is None:
        schema_path = args.schema_path
        database_path = (
            schema_path.resolve(strict=True).parent
            / models.load_schema(schema_path).database
        )
    else:
        database_path = args.database_path

    with open_database(database_path) as db:
        if args.clean:
            db.remove_data_for_missing_files()
        exports = list(db.iter_exports())

    if args.substrings:
        exports = [
            r for r in exports if any(s in r[0].stem for s in args.substrings)
        ]

    table = Table(
        Column("Name", justify="right"),
        "W",
        "H",
        "X←",
        "Y↑",
        "X→",
        "Y↓",
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

    Console().print(table)


def main() -> None:
    suppress_unhandled(KeyboardInterrupt)
    args = parse_args()

    match args:
        case ExportArgs():
            _export_subcommand(args)
        case MetadataArgs():
            _metadata_subcommand(args)
        case JSONSchemaArgs():
            _json_schema_subcommand()


if __name__ == "__main__":
    main()
