from collections.abc import Generator as _Generator
from contextlib import closing as _closing, contextmanager as _contextmanager
from enum import Enum as _Enum, unique as _unique
import os as _os
import re as _re
import sqlite3 as _sqlite3
from sqlite3 import Connection as _Connection, Cursor as _Cursor, Row as _Row
from typing import (
    ContextManager as _ContextManager,
    Literal as _Literal,
    cast as _cast,
    final as _final,
)


def uri(
    filename: _os.PathLike[bytes] | _os.PathLike[str] | str | bytes,
    *,
    vfs: bool | None = None,
    mode: _Literal['ro', 'rw', 'rwc', 'memory'] | None = None,
    cache: _Literal['shared', 'private'] | None = None,
    psow: bool | None = None,
    nolock: bool | None = None,
    immutable: bool | None = None,
) -> str:
    from urllib.request import pathname2url

    parts = [f'file:{pathname2url(str(filename))}']
    options: dict[str, str] = {}

    def set_bool(key: str, value: bool | None) -> None:
        if value is not None:
            options[key] = '1' if value else '0'

    def set_str(key: str, value: str | None) -> None:
        if value is not None:
            options[key] = value

    set_bool('vfs', vfs)
    set_str('mode', mode)
    set_str('cache', cache)
    set_bool('psow', psow)
    set_bool('nolock', nolock)
    set_bool('immutable', immutable)

    if options:
        parts.append('?')
        parts.append('&'.join(f'{k}={v}' for k, v in options.items()))

    return ''.join(parts)


@_final
@_unique
class _Synchronous(_Enum):
    OFF = 'OFF'
    NORMAL = 'NORMAL'
    FULL = 'FULL'
    EXTRA = 'EXTRA'


def _regexp_function(pattern: str, string: str) -> bool:
    return _re.search(pattern, string) is not None


@_contextmanager
def connect(
    database: str | bytes | _os.PathLike[str] | _os.PathLike[bytes],
    *,
    foreign_keys: bool = True,
    readonly: bool = False,
    row_factory: bool = False,
    synchronous: _Literal['off', 'normal', 'full', 'extra'] = 'normal',
    trace: bool = False,
) -> _Generator[_Connection]:
    match _cast(object, synchronous):
        case 'off':
            s = _Synchronous.OFF
        case 'normal':
            s = _Synchronous.NORMAL
        case 'full':
            s = _Synchronous.FULL
        case 'extra':
            s = _Synchronous.EXTRA
        case _:
            raise ValueError(f'invalid synchronous flag {synchronous!r}')
    del synchronous
    if readonly:
        database = uri(database, mode='ro', immutable=True)
    if trace:
        print('Connecting to', database)
    conn = _sqlite3.connect(database, isolation_level=None, uri=readonly)
    with _closing(conn):
        if row_factory:
            conn.row_factory = _Row
        if trace:
            conn.set_trace_callback(print)
        conn.create_function('regexp', 2, _regexp_function, deterministic=True)
        with open_cursor(conn) as cursor:
            cursor.execute(
                f'PRAGMA foreign_keys = {'ON' if foreign_keys else 'OFF'}'
            )
            cursor.execute('PRAGMA journal_mode = WAL')
            cursor.execute(f'PRAGMA synchronous = {s.value}')
            cursor.execute('PRAGMA temp_store = MEMORY')
        yield conn


def open_cursor(connection: _Connection) -> _ContextManager[_Cursor]:
    return _closing(connection.cursor())


@_contextmanager
def transaction(cursor: _Cursor) -> _Generator[None]:
    cursor.execute('BEGIN')
    try:
        yield
    except:
        cursor.execute('ROLLBACK')
        raise
    else:
        cursor.execute('COMMIT')
