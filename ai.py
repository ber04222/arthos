"""Claude-powered analysis ("Ask AI")."""
from __future__ import annotations

import json
import os

import anthropic

MODEL = "claude-sonnet-5-5"

SYSTEM = """You are an experienced Indian equities technical and fundamental analyst.
You receive a JSON snapshot for one NSE stock: latest indicators, detected patterns,
support/resistance, a rule-based trade plan, a score, and valuation bands.
Be concrete and concise. Use INR (₹). Use the numbers given; never invent data.
When asked for an analysis, structure it as:
**Setup** (trend, momentum, key pattern) · **Trade plan** (entry, stop, targets, R:R — adjust the
rule-based plan if you disagree and say why) · **Valuation** · **Risks** · **Confidence** (Low/Med/High).
End with a one-line reminder that this is educational, not financial advice."""


def _secret(name: str) -> str | None:
    """Read from Streamlit secrets (used on Streamlit Community Cloud); None if absent."""
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def get_client(api_key: str | None = None) -> anthropic.Anthropic | None:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY") or _secret("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=key) if key else None


def build_context(symbol: str, result: dict, val: dict | None) -> str:
    df = result["df"]
    last = df.iloc[-1]
    ctx = {
        "symbol": symbol,
        "as_of": str(df.index[-1].date()),
        "price": round(float(last["Close"]), 2),
        "change_1d_pct": round(100 * (df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1), 2),
        "indicators": {k: round(float(last[k]), 2) for k in
                       ["EMA9", "EMA21", "EMA50", "EMA200", "RSI", "MACD", "MACD_signal", "ATR", "BB_up", "BB_lo"]},
        "volume_vs_20d_avg": round(float(last["Volume"] / last["VolSMA20"]), 2),
        "high_52w": round(float(df["High"].iloc[-252:].max()), 2),
        "low_52w": round(float(df["Low"].iloc[-252:].min()), 2),
        "recent_signals": [{"date": str(s["date"].date()), "name": s["name"], "type": s["type"],
                            "detail": s["detail"]} for s in result["signals"][:12]],
        "support": [round(x, 2) for x in result["levels"]["support"]],
        "resistance": [round(x, 2) for x in result["levels"]["resistance"]],
        "rule_based_plan": result["plan"],
        "score": result["score"],
    }
    if val:
        for k in ("pe", "pb"):
            b = val.get(k)
            if b:
                ctx[f"{k}_band"] = {x: round(b[x], 2) for x in
                                    ("current", "min", "max", "median", "buy_below", "sell_above")} | {
                    "verdict": b["verdict"]}
        info = val.get("info", {})
        ctx["fundamentals"] = {k: info.get(k) for k in
                               ("sector", "marketCap", "trailingPE", "priceToBook", "returnOnEquity",
                                "debtToEquity", "profitMargins") if info.get(k) is not None}
    return json.dumps(ctx, default=str)


def stream_chat(client: anthropic.Anthropic, context: str, history: list[dict]):
    """Yields text chunks. history: [{"role": "user"|"assistant", "content": str}, ...]"""
    messages = [{"role": "user", "content": f"Stock snapshot JSON:\n{context}"},
                {"role": "assistant", "content": "Got the snapshot. What would you like to know?"}] + history
    with client.messages.stream(model=MODEL, max_tokens=1500, system=SYSTEM, messages=messages) as stream:
        for text in stream.text_stream:
            yield text
