"""Upbit OHLCV 수집 스크립트.

pyupbit을 이용해 지정된 티커와 인터벌의 캔들 데이터를 가져와
PostgreSQL `price_ohlcv` 테이블에 upsert 합니다. (SQLite fallback 지원)
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional

import pandas as pd
import pyupbit
from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine

load_dotenv()

# ---------------------------------------------------------------------------
# 로깅 설정
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수 정의
# ---------------------------------------------------------------------------

TICKERS = [
    "KRW-BTC",
    "KRW-ETH",
    "KRW-SOL",
    "KRW-DOGE",
    "KRW-XRP",
    "KRW-BNB",
]

INTERVALS = ["minute1", "minute3", "minute5", "minute15", "minute30", "minute60"]
ROW_COUNT = int(os.getenv("OHLCV_ROW_COUNT", "200"))

IS_POSTGRES = engine.url.get_backend_name().startswith("postgres")


metadata = MetaData()

try:
    symbols_table = Table("symbols", metadata, autoload_with=engine)
    price_table = Table("price_ohlcv", metadata, autoload_with=engine)
except SQLAlchemyError as exc:  # pragma: no cover
    raise RuntimeError(f"데이터베이스 스키마를 불러오지 못했습니다: {exc}") from exc


# ---------------------------------------------------------------------------
# 보조 함수
# ---------------------------------------------------------------------------

def _interval_to_timedelta(interval: str) -> timedelta:
    mapping: Dict[str, timedelta] = {
        "minute1": timedelta(minutes=1),
        "minute3": timedelta(minutes=3),
        "minute5": timedelta(minutes=5),
        "minute15": timedelta(minutes=15),
        "minute30": timedelta(minutes=30),
        "minute60": timedelta(minutes=60),
        "minute240": timedelta(minutes=240),
        "day": timedelta(days=1),
    }
    if interval not in mapping:
        raise ValueError(f"지원하지 않는 interval: {interval}")
    return mapping[interval]


def _get_or_create_symbol(session: Session, ticker: str) -> int:
    ticker = ticker.upper()
    symbol_id = session.execute(
        select(symbols_table.c.id).where(symbols_table.c.market_code == ticker)
    ).scalar_one_or_none()
    if symbol_id is not None:
        return symbol_id

    try:
        quote, base = ticker.split("-")
    except ValueError:
        quote, base = "KRW", ticker

    stmt = (
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
    symbol_id = session.execute(stmt).scalar_one()
    session.flush()
    logger.info("Inserted new symbol %s (id=%s)", ticker, symbol_id)
    return symbol_id


def _upsert_ohlcv(
    session: Session,
    symbol_id: int,
    interval: str,
    rows: Iterable[Dict[str, object]],
) -> None:
    stmt_values = [dict(row, symbol_id=symbol_id, interval=interval) for row in rows]
    if not stmt_values:
        return

    if IS_POSTGRES:
        stmt = pg_insert(price_table).values(stmt_values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[price_table.c.symbol_id, price_table.c.interval, price_table.c.open_time],
            set_={
                "close_time": stmt.excluded.close_time,
                "open_price": stmt.excluded.open_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "close_price": stmt.excluded.close_price,
                "volume": stmt.excluded.volume,
                "turnover": stmt.excluded.turnover,
                "collected_at": stmt.excluded.collected_at,
            },
        )
        session.execute(stmt)
    else:
        # SQLite fallback: 개별 upsert
        for value in stmt_values:
            session.execute(
                price_table.insert().prefix_with("OR REPLACE").values(value)
            )


def _fetch_ohlcv(ticker: str, interval: str, count: int) -> pd.DataFrame:
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    if df is None or df.empty:
        logger.warning("No OHLCV data returned for %s (%s)", ticker, interval)
        return pd.DataFrame()
    return df


def _prepare_rows(df: pd.DataFrame, interval: str) -> Iterable[Dict[str, object]]:
    if df.empty:
        return []

    delta = _interval_to_timedelta(interval)
    collected_at = datetime.now(timezone.utc)

    prepared = []
    for open_time, row in df.iterrows():
        if isinstance(open_time, pd.Timestamp):
            open_time_dt = open_time.to_pydatetime()
        else:
            open_time_dt = datetime.fromtimestamp(open_time)

        if open_time_dt.tzinfo is None:
            open_time_dt = open_time_dt.replace(tzinfo=timezone.utc)

        close_time_dt = open_time_dt + delta

        prepared.append(
            {
                "open_time": open_time_dt,
                "close_time": close_time_dt,
                "open_price": float(row["open"]),
                "high_price": float(row["high"]),
                "low_price": float(row["low"]),
                "close_price": float(row["close"]),
                "volume": float(row["volume"]) if not pd.isna(row["volume"]) else None,
                "turnover": float(row["value"]) if "value" in row and not pd.isna(row["value"]) else None,
                "collected_at": collected_at,
            }
        )
    return prepared


# ---------------------------------------------------------------------------
# 데이터 수집 메인 루틴
# ---------------------------------------------------------------------------


def collect_ohlcv(
    tickers: Iterable[str],
    intervals: Iterable[str],
    count: int = ROW_COUNT,
) -> None:
    with SessionLocal() as session:
        for ticker in tickers:
            try:
                symbol_id = _get_or_create_symbol(session, ticker)
            except SQLAlchemyError as exc:
                logger.exception("심볼 확인 중 오류 (%s): %s", ticker, exc)
                session.rollback()
                continue

            for interval in intervals:
                try:
                    df = _fetch_ohlcv(ticker, interval, count)
                    rows = _prepare_rows(df, interval)
                    if not rows:
                        continue

                    _upsert_ohlcv(session, symbol_id, interval, rows)
                    session.commit()
                    logger.info(
                        "OHLCV stored: %s (%s) rows=%d",
                        ticker,
                        interval,
                        len(list(rows)),
                    )
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    logger.exception(
                        "OHLCV 수집 중 오류 발생 (%s / %s): %s",
                        ticker,
                        interval,
                        exc,
                    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Upbit OHLCV collector")
    parser.add_argument(
        "--ticker",
        action="append",
        help="수집할 특정 티커 (여러 번 지정 가능). 미지정 시 기본 TICKERS 사용.",
    )
    parser.add_argument(
        "--interval",
        action="append",
        help="수집할 인터벌 (예: minute1). 미지정 시 기본 INTERVALS 사용.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=ROW_COUNT,
        help=f"수집할 캔들 개수 (기본 {ROW_COUNT})",
    )
    args = parser.parse_args()

    tickers = args.ticker if args.ticker else TICKERS
    intervals = args.interval if args.interval else INTERVALS

    logger.info("Starting OHLCV collection: tickers=%s, intervals=%s", tickers, intervals)
    collect_ohlcv(tickers, intervals, args.count)
    logger.info("Finished OHLCV collection.")


if __name__ == "__main__":
    main()
