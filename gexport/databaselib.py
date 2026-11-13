import os
from collections.abc import Generator as _Generator
from collections.abc import Iterable as _Iterable
from contextlib import contextmanager as _contextmanager
from pathlib import Path as _Path
from sqlite3 import Cursor as _Cursor
from typing import Final as _Final
from typing import NamedTuple as _NamedTuple
from typing import cast as _cast
from typing import final as _final

from gexport.sqlite import connect as _connect
from gexport.sqlite import open_cursor as _open_cursor
from gexport.sqlite import transaction as _transaction


def _initialize(cursor: _Cursor) -> None:
    with _transaction(cursor):
        cursor.execute(r"""
            CREATE TABLE IF NOT EXISTS exports (
                path TEXT PRIMARY KEY
            ,   width INTEGER NOT NULL CHECK (width >= 0)
            ,   height INTEGER NOT NULL CHECK (height >= 0)
            ,   x_offset INTEGER NOT NULL CHECK (x_offset >= 0)
            ,   y_offset INTEGER NOT NULL CHECK (y_offset >= 0)
            ,   x_scale REAL NOT NULL CHECK (x_scale > 0)
            ,   y_scale REAL NOT NULL CHECK (y_scale > 0)
            ) STRICT;
        """)


@_final
class _Export(_NamedTuple):
    path: _Path
    width: int
    height: int
    x_offset: int
    y_offset: int
    x_scale: float
    y_scale: float


type Export = _Export


@_final
class _Database:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor: _Final = cursor

    def get_scale(self, path: _Path) -> tuple[float, float]:
        path_str = os.fspath(path)
        self._cursor.execute(
            'SELECT x_scale, y_scale FROM exports WHERE path = ?', (path_str,)
        )
        row = _cast(tuple[float, float] | None, self._cursor.fetchone())
        if row is None:
            raise ValueError(f'No export with path {path_str!r}')
        return row[0], row[1]

    def iter_exports(self) -> _Iterable[Export]:
        self._cursor.execute(r"""
            SELECT
                path
            ,   width
            ,   height
            ,   x_offset
            ,   y_offset
            ,   x_scale
            ,   y_scale
            FROM exports
            ORDER BY path
        """)

        return (
            _Export(
                _Path(path),  # pyright: ignore[reportAny]
                width,
                height,
                x_offset,
                y_offset,
                x_scale,
                y_scale,
            )
            for path, width, height, x_offset, y_offset, x_scale, y_scale in self._cursor.fetchall()  # pyright: ignore[reportAny]
        )

    def remove_data_for_missing_files(self) -> None:
        with _transaction(self._cursor):
            self._cursor.executemany(
                r'DELETE FROM exports WHERE path = ?',
                (
                    (str(export.path),)
                    for export in self.iter_exports()
                    if not export.path.exists()
                ),
            )

    def save_export(
        self,
        path: _Path,
        width: int,
        height: int,
        x_offset: int,
        y_offset: int,
        x_scale: float,
        y_scale: float,
    ) -> None:
        self._cursor.execute(
            r"""
                INSERT INTO exports VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (path) DO UPDATE SET
                    width = excluded.width
                ,   height = excluded.height
                ,   x_offset = excluded.x_offset
                ,   y_offset = excluded.y_offset
                ,   x_scale = excluded.x_scale
                ,   y_scale = excluded.y_scale

            """,
            (
                str(path),
                width,
                height,
                x_offset,
                y_offset,
                x_scale,
                y_scale,
            ),
        )


type Database = _Database


@_contextmanager
def open_database(path: _Path) -> _Generator[Database]:
    with _connect(path) as conn, _open_cursor(conn) as cursor:
        _initialize(cursor)
        yield _Database(cursor)
