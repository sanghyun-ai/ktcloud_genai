"""SQLite 접속 헬퍼."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from ..config import settings


def _resolve_sqlite_path(database_url: str) -> Optional[Path]:
    """DATABASE_URL 값으로부터 SQLite 파일 경로를 계산한다."""

    if database_url.startswith("sqlite:////"):
        raw_path = "/" + database_url.replace("sqlite:////", "", 1)
    elif database_url.startswith("sqlite:///"):
        raw_path = database_url.replace("sqlite:///", "", 1)
    else:
        return None

    return Path(raw_path).expanduser().resolve()


def get_sqlite_path() -> Path:
    """설정값을 기반으로 SQLite 파일 경로를 반환한다."""

    resolved = _resolve_sqlite_path(settings.database_url)
    if resolved is not None:
        return resolved

    raise ValueError(
        "DATABASE_URL이 sqlite 스킴이 아니므로 SQLite 경로를 계산할 수 없습니다. "
        "예: sqlite:///./indicators.db 형식으로 설정하세요."
    )


@contextmanager
def get_sqlite_connection(row_factory: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """SQLite 연결을 열고 자동으로 닫아주는 컨텍스트 매니저."""

    path = get_sqlite_path()
    conn = sqlite3.connect(path, check_same_thread=False)
    if row_factory:
        conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
