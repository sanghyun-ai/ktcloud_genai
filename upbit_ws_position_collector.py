"""Upbit ticker websocket collector that stores derived position metrics in SQLite.

This script extends the original indicator collector by switching to the
Upbit websocket feed (`pyupbit.WebSocketManager`) and enriching the stored
payload with trading-related metrics such as unrealised PnL, notional value,
liquidation price and exit-plan data. The resulting snapshots are serialised
as JSON and persisted per-ticker in SQLite tables named `positions_<ticker>`.

Configuration notes
-------------------
* Update `POSITIONS_CONFIG` (or provide an external JSON file) with your
  current position details so calculations use accurate values. Each ticker
  key may contain:
    - quantity (base units)
    - entry_price (quote currency)
    - leverage
    - side ("long" or "short")
    - exit_plan (profit target, stop loss, invalidation text)
    - confidence, risk_usd, entry_oid, tp_oid, sl_oid, wait_for_fill
    - liquidation_price (optional override)
* Set `USD_KRW_RATE` (env var) if you prefer a custom USD/KRW conversion rate.
  When possible the script will refresh the rate from Upbit's `USDT-KRW`
  ticker; otherwise it falls back to the configured value.

The script is designed to run continuously until interrupted.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pyupbit


# ---------------------------------------------------------------------------
# Logging & constants
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

DATABASE_FILE = os.getenv("UPBIT_DATABASE_FILE", "./indicators.db")
TABLE_PREFIX = os.getenv("UPBIT_TABLE_PREFIX", "positions_")

# Target tickers (Upbit market codes)
TICKERS = [
    "KRW-BTC",
    "KRW-ETH",
    "KRW-SOL",
    "KRW-DOGE",
    "KRW-XRP",
]


# ---------------------------------------------------------------------------
# Position configuration handling
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
# Helper dataclass & utility functions
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
    """Caches USD/KRW rate with optional Upbit refresh."""

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
# Database helpers
# ---------------------------------------------------------------------------


def _ensure_table(con: sqlite3.Connection, table_name: str) -> None:
    con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            timestamp_key TEXT PRIMARY KEY,
            recorded_at   TEXT,
            json_data     TEXT
        )
        """
    )


def _save_snapshot(con: sqlite3.Connection, ticker: str, payload: Dict[str, Any]) -> None:
    table_name = TABLE_PREFIX + ticker.replace("-", "_")
    _ensure_table(con, table_name)

    timestamp_key = str(payload["timestamp_key"])
    recorded_at = payload["recorded_at"]
    json_blob = json.dumps(payload, ensure_ascii=False)

    con.execute(
        f"""
        INSERT OR REPLACE INTO {table_name} (timestamp_key, recorded_at, json_data)
        VALUES (?, ?, ?)
        """,
        (timestamp_key, recorded_at, json_blob),
    )
    con.commit()
    logging.info("Saved snapshot for %s at %s", ticker, recorded_at)


# ---------------------------------------------------------------------------
# Snapshot construction
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
    else:  # default long
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

    snapshot: Dict[str, Any] = {
        "timestamp_key": trade_timestamp_ms,
        "recorded_at": trade_dt.isoformat(),
        "ticker": ticker,
        "symbol": symbol,
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
# Main data collection loop
# ---------------------------------------------------------------------------


def data_collection_loop(con: sqlite3.Connection) -> None:
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
                    # Avoid duplicate saves for the same trade event
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

                _save_snapshot(con, ticker, snapshot)

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
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        con = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        logging.info("SQLite database connected at %s", DATABASE_FILE)
    except sqlite3.Error as exc:  # noqa: BLE001
        logging.error("Failed to connect to SQLite database: %s", exc)
        raise SystemExit(1) from exc

    try:
        data_collection_loop(con)
    finally:
        con.close()
        logging.info("DB connection closed. Program terminated.")


if __name__ == "__main__":
    main()

