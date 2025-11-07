"""기술 지표 계산 스크립트.

`price_ohlcv` 테이블에 저장된 캔들 데이터를 기반으로 pandas_ta를 이용해
EMA, RSI, MACD, ATR 등의 기술 지표를 계산한 뒤 `indicator_snapshots` 테이블에
JSON 형태로 upsert 합니다.
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

TICKERS = [
    "KRW-BTC",
    "KRW-ETH",
    "KRW-SOL",
    "KRW-DOGE",
    "KRW-XRP",
    "KRW-BNB",
]

INTERVALS = ["minute1", "minute3", "minute5", "minute15", "minute30", "minute60"]
ROW_COUNT = int(os.getenv("INDICATOR_ROW_COUNT", "300"))
SOURCE_NAME = "indicator_computer"

IS_POSTGRES = engine.url.get_backend_name().startswith("postgres")

metadata = MetaData()

try:
    symbols_table = Table("symbols", metadata, autoload_with=engine)
    price_table = Table("price_ohlcv", metadata, autoload_with=engine)
    indicators_table = Table("indicator_snapshots", metadata, autoload_with=engine)
except SQLAlchemyError as exc:  # pragma: no cover
    raise RuntimeError(f"데이터베이스 스키마 로드 실패: {exc}") from exc


# ---------------------------------------------------------------------------
# 보조 함수
# ---------------------------------------------------------------------------


def _resolve_symbol_id(session: Session, ticker: str) -> Optional[int]:
    ticker = ticker.upper()
    symbol_id = session.execute(
        select(symbols_table.c.id).where(symbols_table.c.market_code == ticker)
    ).scalar_one_or_none()
    return symbol_id


def _fetch_price_df(session: Session, symbol_id: int, interval: str, count: int) -> pd.DataFrame:
    stmt = (
        select(
            price_table.c.open_time,
            price_table.c.close_time,
            price_table.c.open_price,
            price_table.c.high_price,
            price_table.c.low_price,
            price_table.c.close_price,
            price_table.c.volume,
            price_table.c.turnover,
        )
        .where(
            price_table.c.symbol_id == symbol_id,
            price_table.c.interval == interval,
        )
        .order_by(price_table.c.open_time.desc())
        .limit(count)
    )
    rows = session.execute(stmt).all()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
    ])
    df.sort_values("open_time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    candles = df.copy()
    candles.ta.ema(length=20, append=True)
    candles.ta.ema(length=50, append=True)
    candles.ta.rsi(length=7, append=True)
    candles.ta.rsi(length=14, append=True)
    candles.ta.macd(append=True)
    candles.ta.atr(length=3, append=True)
    candles.ta.atr(length=14, append=True)
    candles.ta.bbands(length=20, append=True)

    return candles


def _serialize_row(row: pd.Series) -> Dict[str, float]:
    def _float(val: float | int | None) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    indicators = {
        "close": _float(row.get("close")),
        "volume": _float(row.get("volume")),
        "turnover": _float(row.get("turnover")),
        "ema20": _float(row.get("EMA_20")),
        "ema50": _float(row.get("EMA_50")),
        "rsi7": _float(row.get("RSI_7")),
        "rsi14": _float(row.get("RSI_14")),
        "macd": _float(row.get("MACD_12_26_9")),
        "macd_signal": _float(row.get("MACDs_12_26_9")),
        "macd_hist": _float(row.get("MACDh_12_26_9")),
        "atr3": _float(row.get("ATRr_3")),
        "atr14": _float(row.get("ATRr_14")),
        "bb_upper": _float(row.get("BBU_20_2.0")),
        "bb_middle": _float(row.get("BBM_20_2.0")),
        "bb_lower": _float(row.get("BBL_20_2.0")),
    }
    return {k: v for k, v in indicators.items() if v is not None}


def _upsert_indicator(session: Session, symbol_id: int, interval: str, row: pd.Series) -> None:
    recorded_at = row.get("close_time")
    if not isinstance(recorded_at, datetime):
        recorded_at = datetime.fromisoformat(str(recorded_at)).replace(tzinfo=timezone.utc)

    payload = _serialize_row(row)
    payload["interval"] = interval

    if IS_POSTGRES:
        stmt = pg_insert(indicators_table).values(
            symbol_id=symbol_id,
            interval=interval,
            recorded_at=recorded_at,
            indicators=payload,
            source=SOURCE_NAME,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[indicators_table.c.symbol_id, indicators_table.c.interval, indicators_table.c.recorded_at],
            set_={
                "indicators": stmt.excluded.indicators,
                "source": stmt.excluded.source,
            },
        )
        session.execute(stmt)
    else:
        session.execute(
            indicators_table.insert().prefix_with("OR REPLACE").values(
                symbol_id=symbol_id,
                interval=interval,
                recorded_at=recorded_at,
                indicators=payload,
                source=SOURCE_NAME,
            )
        )


# ---------------------------------------------------------------------------
# 메인 루틴
# ---------------------------------------------------------------------------


def compute_indicators(
    tickers: Iterable[str],
    intervals: Iterable[str],
    count: int = ROW_COUNT,
) -> None:
    with SessionLocal() as session:
        for ticker in tickers:
            symbol_id = _resolve_symbol_id(session, ticker)
            if symbol_id is None:
                logger.warning("심볼 %s 을(를) 찾을 수 없습니다. OHLCV를 먼저 수집하세요.", ticker)
                continue

            for interval in intervals:
                try:
                    df = _fetch_price_df(session, symbol_id, interval, count)
                    if df.empty:
                        logger.warning("가격 데이터가 없습니다: %s / %s", ticker, interval)
                        continue

                    computed = _compute_indicators(df)
                    computed = computed.dropna()
                    if computed.empty:
                        logger.warning("지표를 계산할 수 없습니다 (데이터 부족): %s / %s", ticker, interval)
                        continue

                    latest = computed.iloc[-1]
                    _upsert_indicator(session, symbol_id, interval, latest)
                    session.commit()
                    logger.info(
                        "Indicator stored: %s (%s) recorded_at=%s",
                        ticker,
                        interval,
                        latest["close_time"],
                    )
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    logger.exception(
                        "기술 지표 저장 중 오류 발생 (%s / %s): %s",
                        ticker,
                        interval,
                        exc,
                    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Upbit indicator computer")
    parser.add_argument(
        "--ticker",
        action="append",
        help="지표를 계산할 특정 티커 (여러 번 지정 가능). 미지정 시 기본 TICKERS 사용.",
    )
    parser.add_argument(
        "--interval",
        action="append",
        help="지표 계산 인터벌 (예: minute1). 미지정 시 기본 INTERVALS 사용.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=ROW_COUNT,
        help=f"지표 계산에 사용할 캔들 수 (기본 {ROW_COUNT})",
    )
    args = parser.parse_args()

    tickers = args.ticker if args.ticker else TICKERS
    intervals = args.interval if args.interval else INTERVALS

    logger.info("Starting indicator computation: tickers=%s, intervals=%s", tickers, intervals)
    compute_indicators(tickers, intervals, args.count)
    logger.info("Finished indicator computation.")


if __name__ == "__main__":
    main()
