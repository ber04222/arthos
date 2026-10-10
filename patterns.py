"""Pattern & signal detection. Every detector returns a list of signal dicts:
{"date", "name", "type": "bullish"|"bearish"|"neutral", "price", "detail"}
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _sig(df, i, name, kind, detail, price=None):
    return {"date": df.index[i], "name": name, "type": kind,
            "price": float(price if price is not None else df["Close"].iloc[i]), "detail": detail}


def breakouts(df: pd.DataFrame, lookback: int = 60, vol_mult: float = 1.5) -> list[dict]:
    out = []
    start = max(21, len(df) - lookback)
    for i in range(start, len(df)):
        r = df.iloc[i]
        if np.isnan(r["High20"]) or np.isnan(r["VolSMA20"]):
            continue
        vol_ok = r["Volume"] > vol_mult * r["VolSMA20"]
        if r["Close"] > r["High20"] and vol_ok:
            out.append(_sig(df, i, "Breakout", "bullish",
                            f"Closed above 20-day high {r['High20']:.2f} on {r['Volume'] / r['VolSMA20']:.1f}x volume"))
        elif r["Close"] < r["Low20"] and vol_ok:
            out.append(_sig(df, i, "Breakdown", "bearish",
                            f"Closed below 20-day low {r['Low20']:.2f} on {r['Volume'] / r['VolSMA20']:.1f}x volume"))
    return out


def crossovers(df: pd.DataFrame, lookback: int = 60) -> list[dict]:
    out = []
    pairs = [("EMA9", "EMA21", "EMA 9/21"), ("EMA50", "EMA200", None)]
    start = max(1, len(df) - lookback)
    for fast, slow, label in pairs:
        diff = df[fast] - df[slow]
        for i in range(start, len(df)):
            if diff.iloc[i - 1] <= 0 < diff.iloc[i]:
                name = label + " bull cross" if label else "Golden cross"
                out.append(_sig(df, i, name, "bullish", f"{fast} crossed above {slow}"))
            elif diff.iloc[i - 1] >= 0 > diff.iloc[i]:
                name = label + " bear cross" if label else "Death cross"
                out.append(_sig(df, i, name, "bearish", f"{fast} crossed below {slow}"))
    return out


def rsi_signals(df: pd.DataFrame, lookback: int = 30) -> list[dict]:
    out = []
    r = df["RSI"]
    start = max(1, len(df) - lookback)
    for i in range(start, len(df)):
        if r.iloc[i - 1] < 30 <= r.iloc[i]:
            out.append(_sig(df, i, "RSI oversold bounce", "bullish", f"RSI recovered above 30 ({r.iloc[i]:.0f})"))
        elif r.iloc[i - 1] > 70 >= r.iloc[i]:
            out.append(_sig(df, i, "RSI overbought rollover", "bearish", f"RSI fell back below 70 ({r.iloc[i]:.0f})"))
    # simple divergence over last ~30 bars: price makes new low/high, RSI doesn't
    w = df.iloc[-30:]
    if len(w) == 30:
        a, b = w.iloc[:15], w.iloc[15:]
        if b["Low"].min() < a["Low"].min() and w["RSI"].iloc[15:].min() > a["RSI"].min() + 2:
            out.append(_sig(df, len(df) - 1, "Bullish RSI divergence", "bullish",
                            "Price made a lower low but RSI made a higher low"))
        if b["High"].max() > a["High"].max() and w["RSI"].iloc[15:].max() < a["RSI"].max() - 2:
            out.append(_sig(df, len(df) - 1, "Bearish RSI divergence", "bearish",
                            "Price made a higher high but RSI made a lower high"))
    return out


def candlesticks(df: pd.DataFrame, lookback: int = 10) -> list[dict]:
    out = []
    start = max(2, len(df) - lookback)
    for i in range(start, len(df)):
        o, h, l, c = df[["Open", "High", "Low", "Close"]].iloc[i]
        po, ph, pl, pc = df[["Open", "High", "Low", "Close"]].iloc[i - 1]
        body, rng = abs(c - o), max(h - l, 1e-9)
        upper, lower = h - max(o, c), min(o, c) - l
        trend_down = df["Close"].iloc[i - 1] < df["EMA21"].iloc[i - 1]
        if c > o and pc < po and c >= po and o <= pc and body > abs(pc - po):
            out.append(_sig(df, i, "Bullish engulfing", "bullish", "Green body engulfed prior red body"))
        elif c < o and pc > po and o >= pc and c <= po and body > abs(pc - po):
            out.append(_sig(df, i, "Bearish engulfing", "bearish", "Red body engulfed prior green body"))
        elif lower > 2 * body and upper < body and trend_down:
            out.append(_sig(df, i, "Hammer", "bullish", "Long lower wick after decline"))
        elif upper > 2 * body and lower < body and not trend_down:
            out.append(_sig(df, i, "Shooting star", "bearish", "Long upper wick after advance"))
        elif body < 0.1 * rng:
            out.append(_sig(df, i, "Doji", "neutral", "Indecision candle"))
        elif h < ph and l > pl:
            out.append(_sig(df, i, "Inside bar", "neutral", "Range contraction - watch for break"))
    return out


def support_resistance(df: pd.DataFrame, window: int = 5, max_levels: int = 4) -> dict:
    """Swing-pivot levels clustered within 1.5%."""
    highs, lows = df["High"], df["Low"]
    piv_h = [highs.iloc[i] for i in range(window, len(df) - window)
             if highs.iloc[i] == highs.iloc[i - window:i + window + 1].max()]
    piv_l = [lows.iloc[i] for i in range(window, len(df) - window)
             if lows.iloc[i] == lows.iloc[i - window:i + window + 1].min()]
    levels = sorted(piv_h + piv_l)
    clusters: list[list[float]] = []
    for lv in levels:
        if clusters and abs(lv - np.mean(clusters[-1])) / lv < 0.015:
            clusters[-1].append(lv)
        else:
            clusters.append([lv])
    # rank by touches
    ranked = sorted(clusters, key=len, reverse=True)
    px = df["Close"].iloc[-1]
    sup = sorted([float(np.mean(c)) for c in ranked if np.mean(c) < px], reverse=True)[:max_levels]
    res = sorted([float(np.mean(c)) for c in ranked if np.mean(c) > px])[:max_levels]
    return {"support": sup, "resistance": res}


def detect_all(df: pd.DataFrame) -> list[dict]:
    sigs = breakouts(df) + crossovers(df) + rsi_signals(df) + candlesticks(df)
    return sorted(sigs, key=lambda s: s["date"], reverse=True)
