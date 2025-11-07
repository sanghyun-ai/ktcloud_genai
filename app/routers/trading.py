"""전략 시그널 / 주문 / 체결 및 LLM 의사결정 로깅 라우터."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import MetaData, Table, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import engine, get_db

logger = logging.getLogger(__name__)

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
# Pydantic 모델 정의
# ---------------------------------------------------------------------------


class StrategySignalIn(BaseModel):
    ticker: str
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
    order_id: Optional[int]
    trade_id: Optional[str]
    price: float
    quantity: float
    fee: Optional[float]
    liquidity: Optional[str]
    filled_at: Optional[datetime]


class WalletSnapshot(BaseModel):
    cash: Optional[float] = Field(default=None, description="KRW 보유 현금")
    cash_krw: Optional[float] = Field(default=None, description="KRW 보유 현금(대체 필드)")
    holdings: Dict[str, float] = Field(default_factory=dict)
    currency: str = Field("KRW")

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def ensure_cash(cls, values: "WalletSnapshot") -> "WalletSnapshot":
        cash_value = values.cash if values.cash is not None else values.cash_krw
        if cash_value is None:
            raise ValueError("wallet에 cash 또는 cash_krw 값이 필요합니다.")
        values.cash = float(cash_value)
        return values


class LLMDecisionRequest(BaseModel):
    ticker: str
    mode: Optional[str] = "live"
    user_id: Optional[str]
    model_version: Optional[str]
    llm_output: Any
    wallet: WalletSnapshot
    executed_order: Optional[OrderIn] = None
    executed_fill: Optional[OrderFillIn] = None


# ---------------------------------------------------------------------------
# 내부 유틸 함수
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_symbol_id(db: Session, ticker: str) -> int:
    ticker = ticker.upper()
    symbol_id = (
        db.execute(select(symbols_table.c.id).where(symbols_table.c.market_code == ticker))
        .scalar_one_or_none()
    )
    if symbol_id is None:
        raise HTTPException(status_code=404, detail=f"'{ticker}' 심볼이 존재하지 않습니다.")
    return symbol_id


def _create_strategy_signal_entry(db: Session, payload: StrategySignalIn) -> Dict[str, Any]:
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
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"시그널 기록 중 오류: {exc}") from exc

    signal_id = result.scalar_one()
    return {"id": signal_id, "ticker": payload.ticker, **values}


def _create_order_entry(db: Session, payload: OrderIn) -> Dict[str, Any]:
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
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"주문 기록 중 오류: {exc}") from exc

    order_id = result.scalar_one()
    return {"id": order_id, "ticker": payload.ticker, **values}


def _create_order_fill_entry(db: Session, payload: OrderFillIn) -> Dict[str, Any]:
    if payload.order_id is None:
        raise HTTPException(status_code=422, detail="order_fill에는 order_id가 필요합니다.")

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
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"체결 기록 중 오류: {exc}") from exc

    fill_id = result.scalar_one()
    return {"id": fill_id, **values}


def _update_signal_executed_order(db: Session, signal_id: int, order_id: int) -> None:
    try:
        db.execute(
            update(strategy_signals_table)
            .where(strategy_signals_table.c.id == signal_id)
            .values(executed_order_id=order_id)
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"시그널 업데이트 중 오류: {exc}",
        ) from exc


def _parse_llm_output(raw_output: Any) -> Dict[str, Any]:
    data: Mapping[str, Any]
    if isinstance(raw_output, str):
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError as exc:  # noqa: B905
            raise HTTPException(status_code=400, detail=f"LLM 출력 JSON 파싱에 실패했습니다: {exc}") from exc
    elif isinstance(raw_output, Mapping):
        data = raw_output
    else:
        raise HTTPException(status_code=400, detail="LLM 출력은 문자열 또는 JSON 객체여야 합니다.")

    decision_block = data.get("decision")
    if isinstance(decision_block, Mapping):
        merged = {**data, **decision_block}
        data = merged

    action = data.get("action") or data.get("decision")
    if not action:
        raise HTTPException(status_code=400, detail="LLM 출력에 action 정보가 없습니다.")
    action = str(action).lower()

    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    quantity = _coerce_float(
        data.get("quantity") or data.get("amount") or data.get("size")
    )
    price = _coerce_float(data.get("price") or data.get("target_price"))
    confidence = _coerce_float(data.get("confidence") or data.get("score"))

    reasoning = (
        data.get("reasoning")
        or data.get("analysis")
        or data.get("explanation")
        or data.get("commentary")
    )

    ticker = data.get("ticker") or data.get("symbol")
    generated_at_raw = data.get("generated_at")
    generated_at_dt: Optional[datetime] = None
    if isinstance(generated_at_raw, str):
        try:
            generated_at_dt = datetime.fromisoformat(generated_at_raw)
            if generated_at_dt.tzinfo is None:
                generated_at_dt = generated_at_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("generated_at 값을 파싱하지 못했습니다: %s", generated_at_raw)
            generated_at_dt = None

    return {
        "action": action,
        "quantity": quantity,
        "price": price,
        "confidence": confidence,
        "reasoning": reasoning,
        "ticker": ticker,
        "generated_at": generated_at_dt,
        "raw": data,
    }


def _fact_check(
    decision: Dict[str, Any],
    wallet: WalletSnapshot,
    executed_order: Optional[OrderIn],
    actual_ticker: str,
) -> Dict[str, Any]:
    issues: List[str] = []
    action = decision["action"]
    price = decision.get("price")
    quantity = decision.get("quantity")
    decision_ticker = decision.get("ticker")

    if decision_ticker and decision_ticker.upper() != actual_ticker.upper():
        issues.append("decision_ticker_mismatch")

    expected_cost = None
    symbol_token = actual_ticker.split("-")[-1]

    if action in {"buy", "sell"}:
        if price is None or quantity is None:
            issues.append("decision_missing_price_or_quantity")
        else:
            expected_cost = price * quantity
            if action == "buy":
                if wallet.cash is not None and wallet.cash < expected_cost:
                    issues.append("insufficient_cash")
            else:  # sell
                holding_qty = wallet.holdings.get(symbol_token, 0.0)
                if holding_qty + 1e-8 < quantity:
                    issues.append("insufficient_holdings")

    if action in {"buy", "sell"}:
        if executed_order is None:
            issues.append("order_not_executed")
        else:
            if executed_order.side.lower() != action:
                issues.append("executed_side_mismatch")
            if price is not None and executed_order.price is not None:
                if abs(executed_order.price - price) > max(1.0, price * 0.01):
                    issues.append("executed_price_mismatch")
            if quantity is not None:
                if abs(executed_order.quantity - quantity) > max(1e-6, quantity * 0.05):
                    issues.append("executed_quantity_mismatch")

    status = "ok" if not issues else "warning"
    return {
        "status": status,
        "issues": issues,
        "expected_cost": expected_cost,
        "wallet_cash": wallet.cash,
        "wallet_holdings": wallet.holdings,
    }


# ---------------------------------------------------------------------------
# 기본 엔드포인트 (수동 로깅)
# ---------------------------------------------------------------------------


@router.post("/strategy-signals", status_code=status.HTTP_201_CREATED)
def log_strategy_signal(payload: StrategySignalIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    entry = _create_strategy_signal_entry(db, payload)
    db.commit()
    return entry


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def log_order(payload: OrderIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    entry = _create_order_entry(db, payload)
    db.commit()
    return entry


@router.post("/order-fills", status_code=status.HTTP_201_CREATED)
def log_order_fill(payload: OrderFillIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    entry = _create_order_fill_entry(db, payload)
    db.commit()
    return entry


# ---------------------------------------------------------------------------
# LLM 의사결정 입력용 엔드포인트
# ---------------------------------------------------------------------------


@router.post("/llm-decisions", status_code=status.HTTP_201_CREATED)
def ingest_llm_decision(payload: LLMDecisionRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    decision = _parse_llm_output(payload.llm_output)
    fact_check = _fact_check(decision, payload.wallet, payload.executed_order, payload.ticker)

    features = {
        "llm_raw_output": payload.llm_output,
        "parsed_decision": decision["raw"],
        "wallet_snapshot": {
            "cash": payload.wallet.cash,
            "holdings": payload.wallet.holdings,
            "currency": payload.wallet.currency,
        },
    }

    signal_payload = StrategySignalIn(
        ticker=payload.ticker,
        mode=payload.mode,
        user_id=payload.user_id,
        model_version=payload.model_version or decision["raw"].get("model_version"),
        action=decision["action"],
        confidence=decision.get("confidence"),
        reasoning=decision.get("reasoning"),
        features=features,
        decision_meta={"fact_check": fact_check},
        generated_at=decision.get("generated_at"),
    )

    order_result: Optional[Dict[str, Any]] = None
    fill_result: Optional[Dict[str, Any]] = None

    try:
        signal_entry = _create_strategy_signal_entry(db, signal_payload)

        if payload.executed_order:
            order_payload = payload.executed_order.model_copy(
                update={
                    "ticker": payload.executed_order.ticker or payload.ticker,
                    "strategy_signal_id": signal_entry["id"],
                    "status": payload.executed_order.status,
                }
            )
            order_result = _create_order_entry(db, order_payload)
            _update_signal_executed_order(db, signal_entry["id"], order_result["id"])
            signal_entry["executed_order_id"] = order_result["id"]

            if payload.executed_fill:
                fill_payload = payload.executed_fill
                if fill_payload.order_id is None:
                    fill_payload = fill_payload.model_copy(update={"order_id": order_result["id"]})
                fill_result = _create_order_fill_entry(db, fill_payload)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"LLM 결정 처리 중 오류: {exc}") from exc

    response = {
        "signal": signal_entry,
        "order": order_result,
        "fill": fill_result,
        "fact_check": fact_check,
    }
    if fact_check["issues"]:
        response["warnings"] = fact_check["issues"]
    return response
