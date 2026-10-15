"""Turns indicators + signals into a trade plan and a 0-100 score."""
from __future__ import annotations

import pandas as pd

from indicators import add_all
from patterns import detect_all, support_resistance


def trade_plan(df: pd.DataFrame, sigs: list[dict], levels: dict, total_score: int) -> dict:
    last = df.iloc[-1]
    px, a = float(last["Close"]), float(last["ATR"])
    recent = [s for s in sigs if (df.index[-1] - s["date"]).days <= 10]
    bull = sum(1 for s in recent if s["type"] == "bullish")
    bear = sum(1 for s in recent if s["type"] == "bearish")
    uptrend = last["Close"] > last["EMA50"]
    # Bias follows the score; fresh signals only decide borderline cases.
    if total_score >= 55:
        direction = "LONG"
    elif total_score < 45:
        direction = "SHORT"
    else:
        direction = "LONG" if (bull > bear or (bull == bear and uptrend)) else "SHORT"

    if direction == "LONG":
        entry = px
        atr_stop = entry - 1.5 * a
        sup = [s for s in levels["support"] if s < entry]
        stop = max(atr_stop, sup[0] * 0.995) if sup and sup[0] > entry - 3 * a else atr_stop
        risk = entry - stop
        res = [r for r in levels["resistance"] if r > entry + risk]
        t1 = min(entry + 1.5 * risk, res[0]) if res else entry + 1.5 * risk
        t1 = max(t1, entry + risk)
        t2 = entry + 3 * risk
    else:
        entry = px
        atr_stop = entry + 1.5 * a
        res = [r for r in levels["resistance"] if r > entry]
        stop = min(atr_stop, res[0] * 1.005) if res and res[0] < entry + 3 * a else atr_stop
        risk = stop - entry
        sup = [s for s in levels["support"] if s < entry - risk]
        t1 = max(entry - 1.5 * risk, sup[0]) if sup else entry - 1.5 * risk
        t1 = min(t1, entry - risk)
        t2 = entry - 3 * risk
    rr = abs(t2 - entry) / risk if risk else 0
    return {"direction": direction, "entry": round(entry, 2), "stop": round(stop, 2),
            "t1": round(t1, 2), "t2": round(t2, 2), "risk_pct": round(100 * risk / entry, 2), "rr": round(rr, 1)}


def score(df: pd.DataFrame, sigs: list[dict]) -> dict:
    last = df.iloc[-1]
    trend = 0
    trend += 10 if last["Close"] > last["EMA21"] else 0
    trend += 10 if last["Close"] > last["EMA50"] else 0
    trend += 10 if last["Close"] > last["EMA200"] else 0
    trend += 5 if last["EMA50"] > last["EMA200"] else 0
    r = last["RSI"]
    momentum = 20 if 50 <= r <= 70 else 12 if 40 <= r < 50 else 8 if r > 70 else 4
    momentum += 5 if last["MACD_hist"] > 0 else 0
    ret_3m = df["Close"].iloc[-1] / df["Close"].iloc[max(0, len(df) - 63)] - 1
    momentum += min(10, max(0, ret_3m * 50))
    vol_ratio = last["Volume"] / last["VolSMA20"] if last["VolSMA20"] else 1
    volume = min(15, vol_ratio * 7)
    recent = [s for s in sigs if (df.index[-1] - s["date"]).days <= 10]
    pattern = sum(5 for s in recent if s["type"] == "bullish") - sum(5 for s in recent if s["type"] == "bearish")
    pattern = max(-15, min(15, pattern))
    total = max(0, min(100, trend + momentum + volume + pattern))
    return {"score": round(total), "trend": trend, "momentum": round(momentum), "volume": round(volume),
            "pattern": pattern, "ret_3m": round(100 * ret_3m, 1), "rsi": round(float(r), 1)}


def analyze(df_raw: pd.DataFrame) -> dict:
    df = add_all(df_raw)
    sigs = detect_all(df)
    levels = support_resistance(df.iloc[-250:])
    sc = score(df, sigs)
    return {"df": df, "signals": sigs, "levels": levels,
            "plan": trade_plan(df, sigs, levels, sc["score"]), "score": sc}
