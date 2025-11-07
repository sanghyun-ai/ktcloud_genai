"""Upbit 티커 웹소켓 수집기를 통해 파생 포지션 지표를 데이터베이스(PostgreSQL 권장)에 저장합니다.

이 스크립트는 Upbit 웹소켓 피드(`pyupbit.WebSocketManager`)로부터 실시간 체결 정보를 받아
미실현 손익, 명목 가치, 청산가, 청산 계획 등 거래 관련 지표를 계산합니다. 계산된 결과는
`position_snapshots`(JSONB)과 `positions`(정규화된 현재 상태) 테이블에 동시에 기록되어
프론트엔드, LLM 의사결정, 백테스팅에 활용할 수 있습니다.

구성 안내
--------
* 정확한 계산을 위해 `POSITIONS_CONFIG`(또는 외부 JSON 파일)을 최신 포지션 정보로 갱신하세요.
  각 티커 키에는 다음과 같은 값을 포함할 수 있습니다.
    - quantity: 보유 수량(기초 자산 수량)
    - entry_price: 진입가(원화 기준)
    - leverage: 레버리지 배율
    - side: "long" 또는 "short"
    - exit_plan: 목표가, 손절가, 무효화 조건
    - confidence, risk_usd, entry_oid, tp_oid, sl_oid, wait_for_fill
    - liquidation_price: 청산가 수동 입력(선택)
* 사용자 정의 USD/KRW 환율이 필요하면 환경 변수 `USD_KRW_RATE`를 설정하세요. 가능하면
  `USDT-KRW` 실시간 가격으로 환율을 갱신하고, 실패 시 설정값을 사용합니다.

이 스크립트는 중단될 때까지 계속 실행되도록 설계되었습니다.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pyupbit
from sqlalchemy import JSON, MetaData, Table, delete, select
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


# ---------------------------------------------------------------------------
# 로깅 및 상수 설정
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./indicators.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
metadata = MetaData()
IS_POSTGRES = engine.url.get_backend_name().startswith("postgres")

try:
    symbols_table = Table("symbols", metadata, autoload_with=engine)
    position_snapshots_table = Table("position_snapshots", metadata, autoload_with=engine)
    positions_table = Table("positions", metadata, autoload_with=engine)
except SQLAlchemyError as exc:  # pragma: no cover
    logging.error("데이터베이스 스키마를 불러오지 못했습니다. 테이블이 생성되어 있는지 확인하세요: %s", exc)
    raise

# 대상 티커(Upbit 마켓 코드)
TICKERS = [
    "KRW-BTC",
    "KRW-ETH",
    "KRW-SOL",
    "KRW-DOGE",
    "KRW-XRP",
]


# ---------------------------------------------------------------------------
# 포지션 구성 정보 로딩
# ---------------------------------------------------------------------------

POSITIONS_CONFIG_PATH = os.getenv("POSITIONS_CONFIG_PATH", "./positions_config.json")


def _load_positions_config(path: str) -> Dict[str, Dict[str, Any]]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logging.info("Loaded position config from %s", path)
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logging.error("Failed to load position config (%s): %s", path, exc)
    else:
        logging.info("No position config file found at %s; falling back to defaults.", path)
    return {}


DEFAULT_POSITIONS_CONFIG: Dict[str, Dict[str, Any]] = {
    "KRW-XRP": {
        "symbol": "XRP",
        "side": "long",
        "quantity": 5164.0,
        "entry_price": 2.3,
        "leverage": 8,
        "exit_plan": {
            "profit_target": 2.6485,
            "stop_loss": 2.1877,
            "invalidation_condition": "BTC breaks below 105,000...",
        },
        "confidence": 0.62,
        "risk_usd": 594.7,
        "entry_oid": 204655970889,
        "tp_oid": -1,
        "sl_oid": -1,
        "wait_for_fill": False,
        "liquidation_price": 2.07,
    }
}


POSITIONS_CONFIG = {
    **DEFAULT_POSITIONS_CONFIG,
    **_load_positions_config(POSITIONS_CONFIG_PATH),
}


# ---------------------------------------------------------------------------
# 보조 데이터클래스 및 유틸리티 함수
# ---------------------------------------------------------------------------


try:
    from zoneinfo import ZoneInfo

    KST = ZoneInfo("Asia/Seoul")
except Exception:  # pragma: no cover - fallback for Python <3.9
    KST = timezone(timedelta(hours=9))


def _round_or_none(value: Optional[float], digits: int = 8) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return default


def _safe_order_id(value: Any) -> Optional[int]:
    if value in (None, "", -1, "-1"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ticker_to_symbol(ticker: str) -> str:
    return ticker.split("-")[-1]


def _estimate_liquidation_price(
    entry_price: float,
    leverage: float,
    side: str,
    maintenance_margin_rate: float = 0.005,
) -> Optional[float]:
    if leverage is None or leverage <= 0:
        return None
    side_lower = (side or "long").lower()
    adjustment = (1 / leverage) * max(1 - maintenance_margin_rate, 0)
    if side_lower == "long":
        return max(entry_price * (1 - adjustment), 0)
    if side_lower == "short":
        return entry_price * (1 + adjustment)
    return None


def _calculate_risk_usd(
    *,
    side: str,
    entry_price: float,
    stop_loss: Optional[float],
    quantity: float,
    usd_krw_rate: float,
    fallback: Optional[float],
) -> float:
    if fallback is not None:
        return float(fallback)
    if stop_loss is None:
        return 0.0
    side_lower = side.lower()
    if side_lower == "long":
        raw_loss = max(entry_price - stop_loss, 0.0) * quantity
    elif side_lower == "short":
        raw_loss = max(stop_loss - entry_price, 0.0) * quantity
    else:
        raw_loss = 0.0
    if usd_krw_rate <= 0:
        return raw_loss
    return raw_loss / usd_krw_rate


@dataclass
class ExchangeRateCache:
    """Upbit 데이터를 이용해 USD/KRW 환율을 주기적으로 갱신한다."""

    default_rate: float
    refresh_interval: float = float(os.getenv("USD_KRW_REFRESH_SECONDS", "600"))

    def __post_init__(self) -> None:
        self._last_refresh: float = 0.0
        self._value: float = self.default_rate

    def get_rate(self) -> float:
        now = time.monotonic()
        if now - self._last_refresh < self.refresh_interval:
            return self._value
        try:
            price = pyupbit.get_current_price("USDT-KRW")
            if price:
                self._value = float(price)
                self._last_refresh = now
                logging.debug("USD/KRW rate refreshed from Upbit: %.4f", self._value)
                return self._value
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to refresh USD/KRW rate from Upbit: %s", exc)
        # Either failed or interval not elapsed – return current value (default)
        self._last_refresh = now
        return self._value


# ---------------------------------------------------------------------------
# 스냅샷 생성 로직
# ---------------------------------------------------------------------------


def _build_snapshot(
    *,
    ticker: str,
    raw: Dict[str, Any],
    position_cfg: Dict[str, Any],
    usd_krw_rate: float,
) -> Optional[Dict[str, Any]]:
    trade_timestamp_ms = raw.get("trade_timestamp")
    trade_price = raw.get("trade_price")

    if trade_timestamp_ms is None or trade_price is None:
        return None

    try:
        trade_dt = datetime.fromtimestamp(trade_timestamp_ms / 1000, tz=timezone.utc).astimezone(KST)
    except (OSError, OverflowError, ValueError):
        trade_dt = datetime.now(tz=KST)

    symbol = position_cfg.get("symbol") or _ticker_to_symbol(ticker)
    side = (position_cfg.get("side") or "long").lower()
    quantity = float(position_cfg.get("quantity", 0.0))
    entry_price = float(position_cfg.get("entry_price", 0.0))
    leverage = float(position_cfg.get("leverage", 1.0))

    if usd_krw_rate <= 0:
        usd_krw_rate = float(os.getenv("USD_KRW_RATE", "1350.0"))

    notional_usd = 0.0
    if usd_krw_rate > 0:
        notional_usd = (trade_price * quantity) / usd_krw_rate

    if side == "short":
        unrealized_pnl_krw = (entry_price - trade_price) * quantity
    else:  # 기본적으로 롱 포지션으로 간주
        unrealized_pnl_krw = (trade_price - entry_price) * quantity

    unrealized_pnl_usd = (
        unrealized_pnl_krw / usd_krw_rate if usd_krw_rate > 0 else unrealized_pnl_krw
    )

    liquidation_price = position_cfg.get("liquidation_price")
    if liquidation_price is None:
        liquidation_price = _estimate_liquidation_price(entry_price, leverage, side)

    exit_plan = position_cfg.get("exit_plan", {})
    stop_loss = exit_plan.get("stop_loss")

    risk_usd = _calculate_risk_usd(
        side=side,
        entry_price=entry_price,
        stop_loss=stop_loss,
        quantity=quantity,
        usd_krw_rate=usd_krw_rate,
        fallback=position_cfg.get("risk_usd"),
    )

    mode = str(position_cfg.get("mode", "live")).lower()
    status = str(position_cfg.get("status", "open")).lower()
    strategy_tag = position_cfg.get("strategy_tag")

    snapshot: Dict[str, Any] = {
        "timestamp_key": trade_timestamp_ms,
        "recorded_at": trade_dt,
        "ticker": ticker,
        "symbol": symbol,
        "mode": mode,
        "status": status,
        "strategy_tag": strategy_tag,
        "side": side,
        "quantity": _round_or_none(quantity, 6),
        "entry_price": _round_or_none(entry_price, 8),
        "current_price": _round_or_none(trade_price, 8),
        "liquidation_price": _round_or_none(liquidation_price, 8),
        "unrealized_pnl": _round_or_none(unrealized_pnl_usd, 8),
        "leverage": _round_or_none(leverage, 4),
        "notional_usd": _round_or_none(notional_usd, 8),
        "exit_plan": {
            "profit_target": _round_or_none(exit_plan.get("profit_target"), 8),
            "stop_loss": _round_or_none(stop_loss, 8),
            "invalidation_condition": exit_plan.get("invalidation_condition"),
        },
        "confidence": _round_or_none(position_cfg.get("confidence"), 4),
        "risk_usd": _round_or_none(risk_usd, 8),
        "entry_oid": position_cfg.get("entry_oid"),
        "tp_oid": position_cfg.get("tp_oid"),
        "sl_oid": position_cfg.get("sl_oid"),
        "wait_for_fill": _safe_bool(position_cfg.get("wait_for_fill", False)),
        "usd_krw_rate": _round_or_none(usd_krw_rate, 6),
        "source": {
            "trade_volume": _round_or_none(raw.get("trade_volume"), 8),
            "acc_trade_volume": _round_or_none(raw.get("acc_trade_volume"), 4),
            "acc_trade_price": _round_or_none(raw.get("acc_trade_price"), 4),
            "change": raw.get("change"),
            "signed_change_rate": _round_or_none(raw.get("signed_change_rate"), 8),
            "ask_bid": raw.get("ask_bid"),
        },
    }

    return snapshot


# ---------------------------------------------------------------------------
# 데이터베이스 저장 로직
# ---------------------------------------------------------------------------


def _get_or_create_symbol(session: Session, ticker: str) -> int:
    existing = session.execute(
        select(symbols_table.c.id).where(symbols_table.c.market_code == ticker)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    try:
        quote, base = ticker.split("-")
    except ValueError:
        quote, base = "KRW", ticker

    insert_stmt = (
        symbols_table.insert()
        .values(
            market_code=ticker,
            base_asset=base,
            quote_asset=quote,
            display_name=base,
            is_active=True,
        )
        .returning(symbols_table.c.id)
    )
    symbol_id = session.execute(insert_stmt).scalar_one()
    session.flush()
    return symbol_id


def _persist_snapshot(snapshot: Dict[str, Any]) -> None:
    ticker = snapshot["ticker"]
    mode = snapshot.get("mode", "live")
    status = snapshot.get("status", "open")
    exit_plan = snapshot.get("exit_plan", {})
    entry_oid = snapshot.get("entry_oid")
    tp_oid = snapshot.get("tp_oid")
    sl_oid = snapshot.get("sl_oid")
    wait_for_fill = _safe_bool(snapshot.get("wait_for_fill", False))

    recorded_at_value = snapshot.get("recorded_at")
    if isinstance(recorded_at_value, str):
        recorded_at = datetime.fromisoformat(recorded_at_value)
    else:
        recorded_at = recorded_at_value

    payload = snapshot.copy()
    payload["recorded_at"] = recorded_at.isoformat()

    with SessionLocal() as session:
        try:
            symbol_id = _get_or_create_symbol(session, ticker)

            if IS_POSTGRES:
                snapshot_stmt = pg_insert(position_snapshots_table).values(
                    symbol_id=symbol_id,
                    recorded_at=recorded_at,
                    payload=payload,
                    source="collector",
                ).on_conflict_do_nothing(
                    index_elements=["symbol_id", "recorded_at", "source"]
                )
            else:
                snapshot_stmt = position_snapshots_table.insert().values(
                    symbol_id=symbol_id,
                    recorded_at=recorded_at,
                    payload=payload,
                    source="collector",
                )
            session.execute(snapshot_stmt)

            session.execute(
                delete(positions_table).where(
                    positions_table.c.symbol_id == symbol_id,
                    positions_table.c.mode == mode,
                    positions_table.c.status == "open",
                )
            )

            entry_order_id = _safe_order_id(entry_oid)

            session.execute(
                positions_table.insert().values(
                    user_id=None,
                    symbol_id=symbol_id,
                    mode=mode,
                    strategy_tag=snapshot.get("strategy_tag"),
                    status=status,
                    side=snapshot["side"],
                    quantity=snapshot["quantity"],
                    entry_price=snapshot["entry_price"],
                    leverage=snapshot["leverage"],
                    liquidation_price=snapshot["liquidation_price"],
                    stop_loss=exit_plan.get("stop_loss"),
                    take_profit=exit_plan.get("profit_target"),
                    confidence=snapshot.get("confidence"),
                    risk_usd=snapshot.get("risk_usd"),
                    notional_usd=snapshot.get("notional_usd"),
                    entry_timestamp=recorded_at,
                    exit_timestamp=None,
                    pnl_usd=snapshot.get("unrealized_pnl"),
                    current_price=snapshot.get("current_price"),
                    exit_plan_invalidation=exit_plan.get("invalidation_condition"),
                    tp_order_id=_safe_order_id(tp_oid),
                    sl_order_id=_safe_order_id(sl_oid),
                    wait_for_fill=wait_for_fill,
                    extra={
                        "entry_oid": entry_order_id,
                        "entry_oid_raw": entry_oid,
                    },
                )
            )
            session.commit()
            logging.info("Saved snapshot for %s at %s", ticker, recorded_at.isoformat())
        except SQLAlchemyError as exc:
            session.rollback()
            logging.exception("DB 저장 중 오류 발생 (%s): %s", ticker, exc)


# ---------------------------------------------------------------------------
# 메인 데이터 수집 루프
# ---------------------------------------------------------------------------


def data_collection_loop() -> None:
    rate_cache = ExchangeRateCache(default_rate=float(os.getenv("USD_KRW_RATE", "1350.0")))

    while True:
        ws_manager: Optional[pyupbit.WebSocketManager] = None
        try:
            ws_manager = pyupbit.WebSocketManager("ticker", codes=TICKERS)
            last_timestamp_per_ticker: Dict[str, Any] = {}

            logging.info("Subscribed to Upbit ticker websocket for %s", ", ".join(TICKERS))

            while True:
                raw_data = ws_manager.get()
                if not raw_data:
                    continue

                ticker = raw_data.get("code")
                if ticker not in TICKERS:
                    continue

                position_cfg = POSITIONS_CONFIG.get(ticker)
                if not position_cfg:
                    logging.debug("No position config for %s; skipping.", ticker)
                    continue

                trade_timestamp_ms = raw_data.get("trade_timestamp")
                if trade_timestamp_ms is None:
                    continue

                if last_timestamp_per_ticker.get(ticker) == trade_timestamp_ms:
                    # 동일한 체결 이벤트에 대한 중복 저장 방지
                    continue

                last_timestamp_per_ticker[ticker] = trade_timestamp_ms

                usd_rate = rate_cache.get_rate()
                snapshot = _build_snapshot(
                    ticker=ticker,
                    raw=raw_data,
                    position_cfg=position_cfg,
                    usd_krw_rate=usd_rate,
                )

                if snapshot is None:
                    continue

                _persist_snapshot(snapshot)

        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received. Shutting down loop...")
            break
        except Exception as exc:  # noqa: BLE001
            logging.exception("Websocket loop error: %s. Reconnecting in 3 seconds...", exc)
            time.sleep(3)
        finally:
            if ws_manager is not None:
                ws_manager.terminate()


# ---------------------------------------------------------------------------
# 실행 진입점
# ---------------------------------------------------------------------------


def main() -> None:
    logging.info("Starting data collection loop with database URL: %s", DATABASE_URL)
    try:
        data_collection_loop()
    finally:
        logging.info("Program terminated.")


if __name__ == "__main__":
    main()

