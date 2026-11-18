import json
import subprocess
import sys

from suppress_unhandled import suppress_unhandled

from gexport.cli import ExportArgs, JSONSchemaArgs, LayoutArgs, parse_args


def _export_subcommand(args: ExportArgs) -> None:
    from gexport._export import export
    from gexport._layout import print_layout_table
    from gexport._manifest import load_manifest

    try:
        export_paths = export(args.manifest_path, args.substrings)
    except subprocess.CalledProcessError as error:
        code = error.returncode
        raise SystemExit(128 - code if code < 0 else code) from error
    manifest = load_manifest(args.manifest_path)
    print_layout_table(
        manifest.database_path,
        include_export=lambda export: export.path in export_paths,
    )


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
