from collections.abc import Generator as _Generator, Iterable as _Iterable
from contextlib import contextmanager as _contextmanager
from pathlib import Path as _Path
from sqlite3 import Cursor as _Cursor
from typing import Final as _Final, NamedTuple as _NamedTuple, final as _final

from gexport.sqlite import (
    connect as _connect,
    open_cursor as _open_cursor,
    transaction as _transaction,
)


def _initialize(cursor: _Cursor) -> None:
    with _transaction(cursor):
        cursor.execute(r"""
            CREATE TABLE IF NOT EXISTS exports (
                path TEXT PRIMARY KEY
            ,   width INTEGER NOT NULL CHECK (width >= 0)
            ,   height INTEGER NOT NULL CHECK (height >= 0)
            ,   x_offset INTEGER NOT NULL CHECK (x_offset >= 0)
            ,   y_offset INTEGER NOT NULL CHECK (y_offset >= 0)
            ) STRICT;
        """)


@_final
class _Export(_NamedTuple):
    path: _Path
    width: int
    height: int
    x_offset: int
    y_offset: int


type Export = _Export


@_final
class _Database:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor: _Final = cursor

    def iter_exports(self) -> _Iterable[Export]:
        self._cursor.execute(r"""
            SELECT path, width, height, x_offset, y_offset FROM exports
            ORDER BY path
        """)

        return (
            _Export(_Path(path), width, height, x_offset, y_offset)
            for path, width, height, x_offset, y_offset in self._cursor.fetchall()
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
    ) -> None:
        self._cursor.execute(
            r"""
                INSERT INTO exports VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (path) DO UPDATE SET
                    width = excluded.width
                ,   height = excluded.height
                ,   x_offset = excluded.x_offset
                ,   y_offset = excluded.y_offset

            """,
            (str(path), width, height, x_offset, y_offset),
        )


type Database = _Database


@_contextmanager
def open_database(path: _Path) -> _Generator[Database]:
    with _connect(path) as conn, _open_cursor(conn) as cursor:
        _initialize(cursor)
        yield _Database(cursor)
