"""기술 지표 데이터 조회 라우터 (PostgreSQL)."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import MetaData, Table, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import engine, get_db


router = APIRouter(prefix="/indicators", tags=["indicators"])

metadata = MetaData()

try:
    symbols_table = Table("symbols", metadata, autoload_with=engine)
    indicator_snapshots_table = Table("indicator_snapshots", metadata, autoload_with=engine)
except SQLAlchemyError as exc:  # pragma: no cover
    raise RuntimeError(f"데이터베이스 스키마 로드 실패: {exc}") from exc


def _resolve_symbol_id(db: Session, ticker: str) -> int:
    ticker = ticker.upper()
    query = select(symbols_table.c.id).where(symbols_table.c.market_code == ticker)
    symbol_id = db.execute(query).scalar_one_or_none()
    if symbol_id is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' 심볼이 존재하지 않습니다.")
    return symbol_id


def _serialize_indicator_row(row: Dict) -> Dict:
    indicators = row.get("indicators") or {}
    indicators["timestamp"] = row.get("recorded_at")
    indicators["interval"] = row.get("interval")
    return indicators


@router.get("/{ticker}/latest")
def get_latest_indicator(
    ticker: str,
    db: Session = Depends(get_db),
) -> Dict:
    """지정한 티커의 최신 기술 지표 데이터를 반환."""

    symbol_id = _resolve_symbol_id(db, ticker)
    stmt = (
        select(
            indicator_snapshots_table.c.interval,
            indicator_snapshots_table.c.recorded_at,
            indicator_snapshots_table.c.indicators,
        )
        .where(indicator_snapshots_table.c.symbol_id == symbol_id)
        .order_by(indicator_snapshots_table.c.recorded_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' 기술 지표 데이터가 존재하지 않습니다.")

    return _serialize_indicator_row(dict(row))


@router.get("/{ticker}")
def get_recent_indicators(
    ticker: str,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> List[Dict]:
    """최신 순으로 여러 기술 지표 스냅샷을 반환."""

    if limit <= 0 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit 값은 1~1000 사이여야 합니다.")

    symbol_id = _resolve_symbol_id(db, ticker)
    stmt = (
        select(
            indicator_snapshots_table.c.interval,
            indicator_snapshots_table.c.recorded_at,
            indicator_snapshots_table.c.indicators,
        )
        .where(indicator_snapshots_table.c.symbol_id == symbol_id)
        .order_by(indicator_snapshots_table.c.recorded_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).mappings().all()
    return [_serialize_indicator_row(dict(row)) for row in rows]
