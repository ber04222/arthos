"""Technical indicators in plain pandas."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(), (df["Low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"]
    for n in (9, 21, 50, 200):
        df[f"EMA{n}"] = ema(c, n)
    df["RSI"] = rsi(c)
    macd = ema(c, 12) - ema(c, 26)
    df["MACD"] = macd
    df["MACD_signal"] = ema(macd, 9)
    df["MACD_hist"] = macd - df["MACD_signal"]
    df["ATR"] = atr(df)
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    df["BB_mid"], df["BB_up"], df["BB_lo"] = mid, mid + 2 * sd, mid - 2 * sd
    df["VolSMA20"] = df["Volume"].rolling(20).mean()
    df["High20"] = df["High"].rolling(20).max().shift()
    df["Low20"] = df["Low"].rolling(20).min().shift()
    return df
