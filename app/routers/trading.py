"""전략 시그널 / 주문 / 체결 로깅 라우터."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, Table, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import engine, get_db


router = APIRouter(prefix="/trading", tags=["trading"])

metadata = MetaData()

try:
    symbols_table = Table("symbols", metadata, autoload_with=engine)
    strategy_signals_table = Table("strategy_signals", metadata, autoload_with=engine)
    orders_table = Table("orders", metadata, autoload_with=engine)
    order_fills_table = Table("order_fills", metadata, autoload_with=engine)
except SQLAlchemyError as exc:  # pragma: no cover
    raise RuntimeError(f"데이터베이스 스키마 로드 실패: {exc}") from exc


# ---------------------------------------------------------------------------
# Pydantic 입력 모델
# ---------------------------------------------------------------------------


class StrategySignalIn(BaseModel):
    ticker: str = Field(..., description="KRW 마켓 코드 (예: KRW-BTC)")
    mode: Optional[str] = Field("live", description="live / simulation")
    user_id: Optional[str]
    model_version: Optional[str]
    action: str = Field(..., description="buy / hold / sell")
    confidence: Optional[float] = Field(None, ge=0.0)
    reasoning: Optional[str]
    features: Optional[Dict[str, Any]]
    decision_meta: Optional[Dict[str, Any]]
    executed_order_id: Optional[int]
    generated_at: Optional[datetime]


class OrderIn(BaseModel):
    ticker: str
    user_id: Optional[str]
    position_id: Optional[int]
    strategy_signal_id: Optional[int]
    external_order_id: Optional[str]
    side: str = Field(..., description="buy / sell")
    order_type: str = Field(..., description="market / limit / ...")
    price: Optional[float]
    quantity: float
    status: str = Field(..., description="placed / filled / cancelled ...")
    placed_at: Optional[datetime]
    meta: Optional[Dict[str, Any]]


class OrderFillIn(BaseModel):
    order_id: int
    trade_id: Optional[str]
    price: float
    quantity: float
    fee: Optional[float]
    liquidity: Optional[str]
    filled_at: Optional[datetime]


# ---------------------------------------------------------------------------
# 유틸 함수
# ---------------------------------------------------------------------------


def _resolve_symbol_id(db: Session, ticker: str) -> int:
    ticker = ticker.upper()
    symbol_id = (
        db.execute(select(symbols_table.c.id).where(symbols_table.c.market_code == ticker))
        .scalar_one_or_none()
    )
    if symbol_id is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' 심볼이 존재하지 않습니다.")
    return symbol_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.post("/strategy-signals", status_code=status.HTTP_201_CREATED)
def log_strategy_signal(payload: StrategySignalIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """LLM / 전략 모델이 생성한 시그널을 기록."""

    symbol_id = _resolve_symbol_id(db, payload.ticker)
    generated_at = payload.generated_at or _now()

    values = {
        "symbol_id": symbol_id,
        "user_id": payload.user_id,
        "mode": (payload.mode or "live").lower(),
        "generated_at": generated_at,
        "model_version": payload.model_version,
        "action": payload.action.lower(),
        "confidence": payload.confidence,
        "reasoning": payload.reasoning,
        "features": payload.features,
        "decision_meta": payload.decision_meta,
        "executed_order_id": payload.executed_order_id,
    }

    try:
        result = db.execute(
            strategy_signals_table.insert().values(**values).returning(strategy_signals_table.c.id)
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"시그널 기록 중 오류: {exc}") from exc

    signal_id = result.scalar_one()
    return {"id": signal_id, **values}


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def log_order(payload: OrderIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """실제 주문(또는 시뮬레이션 주문)을 기록."""

    symbol_id = _resolve_symbol_id(db, payload.ticker)
    placed_at = payload.placed_at or _now()

    values = {
        "user_id": payload.user_id,
        "symbol_id": symbol_id,
        "strategy_signal_id": payload.strategy_signal_id,
        "position_id": payload.position_id,
        "external_order_id": payload.external_order_id,
        "side": payload.side.lower(),
        "order_type": payload.order_type.lower(),
        "price": payload.price,
        "quantity": payload.quantity,
        "status": payload.status.lower(),
        "placed_at": placed_at,
        "meta": payload.meta,
    }

    try:
        result = db.execute(orders_table.insert().values(**values).returning(orders_table.c.id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"주문 기록 중 오류: {exc}") from exc

    order_id = result.scalar_one()
    return {"id": order_id, **values}


@router.post("/order-fills", status_code=status.HTTP_201_CREATED)
def log_order_fill(payload: OrderFillIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """주문 체결 내역을 기록."""

    filled_at = payload.filled_at or _now()
    values = {
        "order_id": payload.order_id,
        "trade_id": payload.trade_id,
        "price": payload.price,
        "quantity": payload.quantity,
        "fee": payload.fee,
        "liquidity": payload.liquidity,
        "filled_at": filled_at,
    }

    try:
        result = db.execute(
            order_fills_table.insert().values(**values).returning(order_fills_table.c.id)
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"체결 기록 중 오류: {exc}") from exc

    fill_id = result.scalar_one()
    return {"id": fill_id, **values}
