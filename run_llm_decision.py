from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Optional

import requests
from openai import OpenAI
from sqlalchemy import MetaData, Table, select

from app.database import SessionLocal, engine

SYSTEM_PROMPT = """
You are an expert AI trading analyst. Your goal is to analyze the market data provided and decide on a single, actionable trade.

You MUST follow this exact process:

1.  **Think (Chain-of-Thought):**
    First, think step-by-step about the provided data. Your thought process must be private, inside <thinking>...</thinking> tags.
    Your analysis MUST cover:
    - Current Position Analysis: Review any existing positions, PnL, and invalidation conditions.
    - Market Analysis: Analyze the provided data for BTC and other major coins (ETH, SOL, etc.).
    - Strategic Assessment: Synthesize all data to find the best trading opportunity.
    - Actionable Decision: Formulate a specific, justified trade with risk parameters.

2.  **Act (JSON Output):**
    After your <thinking> block, you MUST output ONLY a single JSON object with the trade decision.
    Do NOT write any other text or explanation outside the JSON block.
    The JSON structure MUST be:

    {
        "stop_loss": <float>,
        "signal": "<buy_to_enter | sell_to_enter | hold | close_position>",
        "leverage": <int>,
        "risk_usd": <float>,
        "profit_target": <float>,
        "quantity": <float>,
        "invalidation_condition": "<string>",
        "justification": "<string - a brief summary of your CoT rationale>",
        "confidence": <float between 0.0 and 1.0>,
        "coin": "<string, e.g., BTC, ETH>"
    }
"""

TRADING_ENDPOINT = "http://localhost:8000/api/v1/trading/llm-decisions"

client = OpenAI(
    base_url="https://unmummied-keshia-feelingly.ngrok-free.dev/v1",
    api_key="",
)

metadata = MetaData()
symbols_table = Table("symbols", metadata, autoload_with=engine)
positions_table = Table("positions", metadata, autoload_with=engine)
indicator_table = Table("indicator_snapshots", metadata, autoload_with=engine)


def fetch_latest_state(ticker: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        symbol_id = session.execute(
            select(symbols_table.c.id).where(symbols_table.c.market_code == ticker)
        ).scalar_one_or_none()
        if symbol_id is None:
            raise RuntimeError(f"'{ticker}' 심볼을 찾을 수 없습니다.")

        pos = (
            session.execute(
                select(positions_table)
                .where(positions_table.c.symbol_id == symbol_id)
                .order_by(positions_table.c.entry_timestamp.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        ind = (
            session.execute(
                select(indicator_table)
                .where(indicator_table.c.symbol_id == symbol_id)
                .order_by(indicator_table.c.recorded_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return {
            "position": dict(pos) if pos else None,
            "indicator": dict(ind) if ind else None,
        }


def build_prompt(state: Dict[str, Any]) -> str:
    position = state["position"] or {}
    indicator_row = state["indicator"] or {}
    indicators = indicator_row.get("indicators", {})

    prompt = f"""
It has been 2399 minute since you started trading.

### CURRENT MARKET STATE
current_price = {indicators.get('close')}
current_ema20 = {indicators.get('ema20')}
current_rsi7 = {indicators.get('rsi7')}
current_macd = {indicators.get('macd')}

### ACCOUNT INFORMATION & PERFORMANCE
Current live positions & performance:
{position}
"""
    return prompt


def extract_json_block(model_output: str) -> Dict[str, Any]:
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", model_output, flags=re.DOTALL)
    match = re.search(r"\{[\s\S]+\}", cleaned)
    if not match:
        raise ValueError("응답에서 JSON 블록을 찾지 못했습니다.")
    payload = json.loads(match.group())
    required = {
        "stop_loss",
        "signal",
        "leverage",
        "risk_usd",
        "profit_target",
        "quantity",
        "invalidation_condition",
        "justification",
        "confidence",
        "coin",
    }
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"LLM 출력에 필요한 필드가 없습니다: {missing}")
    return payload


def signal_to_side(signal: str) -> Optional[str]:
    mapping = {
        "buy_to_enter": "buy",
        "sell_to_enter": "sell",
        "close_position": "sell",
        "hold": None,
    }
    return mapping.get(signal)


def post_llm_decision(
    llm_json: Dict[str, Any],
    wallet_snapshot: Dict[str, Any],
    executed_price: Optional[float] = None,
):
    signal = llm_json["signal"]
    side = signal_to_side(signal)
    ticker = f"KRW-{llm_json['coin'].upper()}"

    executed_order = None
    executed_fill = None
    if side:
        executed_price = executed_price or llm_json["stop_loss"]
        executed_order = {
            "ticker": ticker,
            "side": side,
            "order_type": "market",
            "price": executed_price,
            "quantity": llm_json["quantity"],
            "status": "filled",
        }
        executed_fill = {
            "order_id": None,
            "price": executed_price,
            "quantity": llm_json["quantity"],
            "fee": llm_json["quantity"] * executed_price * 0.0005,
            "liquidity": "taker",
        }

    payload = {
        "ticker": ticker,
        "mode": "live",
        "user_id": "agent-001",
        "model_version": "gemma-3-27b-it",
        "llm_output": llm_json,
        "wallet": wallet_snapshot,
        "executed_order": executed_order,
        "executed_fill": executed_fill,
    }

    resp = requests.post(TRADING_ENDPOINT, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main():
    state = fetch_latest_state("KRW-BTC")
    prompt = build_prompt(state)

    start = time.perf_counter()
    completion = client.chat.completions.create(
        model="google/gemma-3-27b-it",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    elapsed = time.perf_counter() - start
    print(f"[INFO] vLLM 응답 시간: {elapsed:.4f} 초")

    model_output = completion.choices[0].message.content
    print("\n--- Raw Model Output ---")
    print(model_output)

    llm_json = extract_json_block(model_output)

    position = state["position"] or {}
    wallet_snapshot = {
        "cash": position.get("notional_usd", 0.0),
        "holdings": {position.get("symbol", "XRP"): position.get("quantity", 0.0)},
        "currency": "KRW",
    }

    result = post_llm_decision(llm_json, wallet_snapshot, executed_price=None)

    print("\n=== 저장 결과 ===")
    print("Signal:", result["signal"])
    print("Order :", result["order"])
    print("Fill  :", result["fill"])
    print("Fact-check:", result["fact_check"])
    if result.get("warnings"):
        print("Warnings:", result["warnings"])


if __name__ == "__main__":
    main()
