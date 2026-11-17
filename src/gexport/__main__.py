import json
import sys

from gexport import models
from gexport._gimp import GIMP
from gexport.cli import ExportArgs, JSONSchemaArgs, LayoutArgs, parse_args
from gexport.util import suppress_unhandled


def _export_subcommand(args: ExportArgs) -> None:
    gimp = GIMP(manifest_path=args.manifest_path, substrings=args.substrings)
    print(gimp.make_shell_command())
    gimp.exec()


def _json_schema_subcommand() -> None:
    json.dump(models.Manifest.model_json_schema(), sys.stdout, indent=2)


def main() -> None:
    suppress_unhandled(KeyboardInterrupt)
    args = parse_args()

    match args:
        case ExportArgs():
            _export_subcommand(args)
        case LayoutArgs():
            from gexport._layout import layout_subcommand

            layout_subcommand(args)
        case JSONSchemaArgs():
            _json_schema_subcommand()


if __name__ == "__main__":
    main()
