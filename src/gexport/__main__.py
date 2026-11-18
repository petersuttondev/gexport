import json
import subprocess
import sys

from gexport.cli import ExportArgs, JSONSchemaArgs, LayoutArgs, parse_args
from gexport.util import suppress_unhandled


def _export_subcommand(args: ExportArgs) -> None:
    from gexport._gimp import GIMP

    gimp = GIMP(manifest_path=args.manifest_path, substrings=args.substrings)
    print(gimp.make_shell_command())
    try:
        gimp.run()
    except subprocess.CalledProcessError as error:
        code = error.returncode
        raise SystemExit(128 - code if code < 0 else code) from error


def _json_schema_subcommand() -> None:
    from gexport import models

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
