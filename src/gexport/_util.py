import os
import textwrap

type StrPathLike = os.PathLike[str] | str


def heredoc(text: str) -> str:
    return textwrap.dedent(text).strip()
