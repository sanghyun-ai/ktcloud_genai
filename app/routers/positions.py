"""포지션 데이터 조회 라우터."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException

from ..services.sqlite import get_sqlite_connection


router = APIRouter(prefix="/positions", tags=["positions"])


def _table_name_for_ticker(ticker: str) -> str:
    return f"positions_{ticker.replace('-', '_')}"


@router.get("/{ticker}/latest")
def get_latest_position(ticker: str) -> dict[str, Any]:
    """지정한 티커의 최신 포지션 스냅샷을 반환."""

    table_name = _table_name_for_ticker(ticker)
    query = f"SELECT timestamp_key, recorded_at, json_data FROM {table_name} ORDER BY timestamp_key DESC LIMIT 1"

    try:
        with get_sqlite_connection(row_factory=True) as conn:
            cursor = conn.execute(query)
            row = cursor.fetchone()
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=404, detail=f"테이블 '{table_name}' 조회에 실패했습니다: {exc}") from exc

    if row is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' 포지션 데이터가 존재하지 않습니다.")

    try:
        payload = json.loads(row["json_data"])  # type: ignore[index]
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="DB에 저장된 JSON을 파싱할 수 없습니다.") from exc

    payload["timestamp_key"] = row["timestamp_key"]  # type: ignore[index]
    payload["recorded_at"] = row["recorded_at"]  # type: ignore[index]
    return payload


@router.get("/{ticker}")
def get_recent_positions(ticker: str, limit: int = 50) -> list[dict[str, Any]]:
    """최신 순으로 여러 포지션 스냅샷을 반환."""

    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit 값은 1~500 사이여야 합니다.")

    table_name = _table_name_for_ticker(ticker)
    query = f"SELECT timestamp_key, recorded_at, json_data FROM {table_name} ORDER BY timestamp_key DESC LIMIT ?"

    try:
        with get_sqlite_connection(row_factory=True) as conn:
            cursor = conn.execute(query, (limit,))
            rows = cursor.fetchall()
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=404, detail=f"테이블 '{table_name}' 조회에 실패했습니다: {exc}") from exc

    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["json_data"])  # type: ignore[index]
        except (TypeError, json.JSONDecodeError):
            continue
        payload["timestamp_key"] = row["timestamp_key"]  # type: ignore[index]
        payload["recorded_at"] = row["recorded_at"]  # type: ignore[index]
        results.append(payload)

    return results
