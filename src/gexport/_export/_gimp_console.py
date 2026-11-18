import os
import subprocess
import sys
from collections import ChainMap
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory

from gexport._export._ipc import make_export_request, read_export_response
from gexport._util import heredoc


def export(
    manifest_path: Path,
    substrings: Iterable[str] | None = None,
) -> list[Path]:
    batch = heredoc(f"""
        import sys
        sys.path.extend({sys.path!r})
        from gexport._export._script import run
        run()
    """)
    with TemporaryDirectory() as working_dir:
        subprocess.run(
            (
                "gimp-console",
                "--new-instance",
                "--no-data",
                "--no-fonts",
                "--no-splash",
                f"--batch={batch}",
                "--batch-interpreter=python-fu-eval",
                "--quit",
            ),
            env=ChainMap(
                make_export_request(manifest_path, working_dir, substrings),
                os.environ,
            ),
            check=True,
        )
        response = read_export_response(working_dir)
    return response.export_paths
