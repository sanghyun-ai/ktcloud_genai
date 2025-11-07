"""포지션 데이터 조회 라우터 (PostgreSQL)."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import MetaData, Table, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import engine, get_db


router = APIRouter(prefix="/positions", tags=["positions"])

metadata = MetaData()

try:
    symbols_table = Table("symbols", metadata, autoload_with=engine)
    positions_table = Table("positions", metadata, autoload_with=engine)
except SQLAlchemyError as exc:  # pragma: no cover
    raise RuntimeError(f"데이터베이스 스키마 로드 실패: {exc}") from exc


def _normalize(value: str | None, default: str) -> str:
    if not value:
        return default
    return value.lower()


def _serialize_position_row(row: Dict[str, Any]) -> Dict[str, Any]:
    exit_plan = {
        "profit_target": row.get("take_profit"),
        "stop_loss": row.get("stop_loss"),
        "invalidation_condition": row.get("exit_plan_invalidation"),
    }

    def _float(val: Any) -> float | None:
        return float(val) if val is not None else None

    return {
        "symbol_id": row["symbol_id"],
        "mode": _normalize(row.get("mode"), "live"),
        "status": _normalize(row.get("status"), "open"),
        "strategy_tag": row.get("strategy_tag"),
        "side": row.get("side"),
        "quantity": _float(row.get("quantity")),
        "entry_price": _float(row.get("entry_price")),
        "current_price": _float(row.get("current_price")),
        "liquidation_price": _float(row.get("liquidation_price")),
        "unrealized_pnl": _float(row.get("pnl_usd")),
        "leverage": _float(row.get("leverage")),
        "notional_usd": _float(row.get("notional_usd")),
        "confidence": _float(row.get("confidence")),
        "risk_usd": _float(row.get("risk_usd")),
        "exit_plan": exit_plan,
        "entry_timestamp": row.get("entry_timestamp"),
        "exit_timestamp": row.get("exit_timestamp"),
        "tp_oid": row.get("tp_order_id"),
        "sl_oid": row.get("sl_order_id"),
        "wait_for_fill": row.get("wait_for_fill"),
        "extra": row.get("extra") or {},
    }


def _resolve_symbol_id(db: Session, ticker: str) -> int:
    ticker = ticker.upper()
    query = select(symbols_table.c.id).where(symbols_table.c.market_code == ticker)
    symbol_id = db.execute(query).scalar_one_or_none()
    if symbol_id is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' 심볼이 존재하지 않습니다.")
    return symbol_id


def _base_position_select(symbol_id: int):
    return (
        select(
            positions_table.c.symbol_id,
            positions_table.c.mode,
            positions_table.c.status,
            positions_table.c.strategy_tag,
            positions_table.c.side,
            positions_table.c.quantity,
            positions_table.c.entry_price,
            positions_table.c.current_price,
            positions_table.c.liquidation_price,
            positions_table.c.pnl_usd,
            positions_table.c.leverage,
            positions_table.c.notional_usd,
            positions_table.c.confidence,
            positions_table.c.risk_usd,
            positions_table.c.stop_loss,
            positions_table.c.take_profit,
            positions_table.c.exit_plan_invalidation,
            positions_table.c.entry_timestamp,
            positions_table.c.exit_timestamp,
            positions_table.c.tp_order_id,
            positions_table.c.sl_order_id,
            positions_table.c.wait_for_fill,
            positions_table.c.extra,
        ).where(positions_table.c.symbol_id == symbol_id)
    )


@router.get("/{ticker}/latest")
def get_latest_position(
    ticker: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """지정한 티커의 최신 포지션 상태를 반환."""

    symbol_id = _resolve_symbol_id(db, ticker)
    stmt = (
        _base_position_select(symbol_id)
        .where(positions_table.c.status == "open")
        .order_by(positions_table.c.entry_timestamp.desc())
        .limit(1)
    )
    row = db.execute(stmt).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' 포지션 데이터가 존재하지 않습니다.")
    return _serialize_position_row(dict(row))


@router.get("/{ticker}")
def get_recent_positions(
    ticker: str,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """최신 순으로 여러 포지션 스냅샷을 반환."""

    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit 값은 1~500 사이여야 합니다.")

    symbol_id = _resolve_symbol_id(db, ticker)
    stmt = (
        _base_position_select(symbol_id)
        .order_by(positions_table.c.entry_timestamp.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).mappings().all()
    return [_serialize_position_row(dict(row)) for row in rows]
