"""Market data access via yfinance, with a synthetic demo fallback."""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

NIFTY50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO",
    "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL", "BPCL", "BRITANNIA", "CIPLA",
    "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL", "GRASIM", "HCLTECH", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK",
    "INFY", "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT", "M&M", "MARUTI",
    "NESTLEIND", "NTPC", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN",
    "SHRIRAMFIN", "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
]
NIFTY_INDEX = "^NSEI"
NIFTY_ETF = "NIFTYBEES.NS"

PERIODS = {"6M": "6mo", "1Y": "1y", "3Y": "3y", "5Y": "5y"}


def to_symbol(name: str) -> str:
    name = name.strip().upper()
    if name.startswith("^") or "." in name:
        return name
    return f"{name}.NS"


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def get_history(symbol: str, period: str = "1y", demo: bool = False) -> pd.DataFrame:
    if demo:
        return demo_history(symbol, period)
    df = yf.download(symbol, period=period, interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    return _clean(df)


@st.cache_data(ttl=900, show_spinner=False)
def get_many(symbols: tuple[str, ...], period: str = "1y", demo: bool = False) -> dict[str, pd.DataFrame]:
    """Batched download for scanning. Returns {symbol: OHLCV}."""
    if demo:
        return {s: demo_history(s, period) for s in symbols}
    raw = yf.download(list(symbols), period=period, interval="1d", auto_adjust=True,
                      group_by="ticker", progress=False, threads=True)
    out = {}
    if raw is None or raw.empty:
        return out
    for s in symbols:
        try:
            df = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
            df = _clean(df.copy())
            if len(df) > 60:
                out[s] = df
        except KeyError:
            continue
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def get_fundamentals(symbol: str, demo: bool = False) -> dict:
    """Returns info dict plus annual EPS / book-value-per-share series (may be empty)."""
    if demo:
        return demo_fundamentals(symbol)
    t = yf.Ticker(symbol)
    result = {"info": {}, "eps": pd.Series(dtype=float), "bvps": pd.Series(dtype=float)}
    try:
        result["info"] = t.info or {}
    except Exception:
        pass
    try:
        inc = t.income_stmt
        for row in ("Diluted EPS", "Basic EPS"):
            if row in inc.index:
                result["eps"] = inc.loc[row].dropna().sort_index()
                break
    except Exception:
        pass
    try:
        bs = t.balance_sheet
        shares_row = next((r for r in ("Ordinary Shares Number", "Share Issued") if r in bs.index), None)
        eq_row = next((r for r in ("Stockholders Equity", "Common Stock Equity") if r in bs.index), None)
        if shares_row and eq_row:
            result["bvps"] = (bs.loc[eq_row] / bs.loc[shares_row]).dropna().sort_index()
    except Exception:
        pass
    return result


@st.cache_data(ttl=300, show_spinner=False)
def get_index_quote(demo: bool = False) -> dict | None:
    """Latest Nifty 50 close and day change for the header."""
    df = demo_history(NIFTY_INDEX, "6mo") if demo else get_history(NIFTY_INDEX, "1mo")
    if df is None or len(df) < 2:
        return None
    last, prev = float(df["Close"].iloc[-1]), float(df["Close"].iloc[-2])
    return {"price": last, "change": last - prev, "pct": 100 * (last / prev - 1), "date": df.index[-1]}


# --------------------------------------------------------------------------
# Demo data: deterministic per-symbol random walks, used when Yahoo is
# unreachable or when the user ticks "Demo data". Not real prices.
# --------------------------------------------------------------------------
_PERIOD_DAYS = {"6mo": 126, "1y": 252, "2y": 504, "3y": 756, "5y": 1260}


def demo_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    n = _PERIOD_DAYS.get(period, 252)
    full = 1260
    rng = np.random.default_rng(zlib.crc32(symbol.encode()))
    drift = rng.normal(0.0004, 0.0006)
    vol = rng.uniform(0.012, 0.025) if not symbol.startswith("^") else 0.008
    rets = rng.normal(drift, vol, full)
    # inject a few regime shifts so patterns/breakouts appear
    for _ in range(4):
        i = rng.integers(50, full - 30)
        rets[i:i + 20] += rng.normal(0, 0.006)
    base = 18000 if symbol.startswith("^") else rng.uniform(200, 4000)
    close = base * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, vol / 3, full))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, vol / 2, full)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, vol / 2, full)))
    volume = rng.lognormal(14, 0.4, full) * (1 + 3 * np.abs(rets) / vol * 0.3)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=full)
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                       "Volume": volume.astype(int)}, index=idx)
    return df.iloc[-n:]


def demo_fundamentals(symbol: str) -> dict:
    rng = np.random.default_rng(zlib.crc32((symbol + "f").encode()))
    px = demo_history(symbol, "5y")["Close"]
    years = pd.to_datetime([f"{y}-03-31" for y in range(px.index[0].year, px.index[-1].year + 1)])
    base_pe = rng.uniform(12, 60)
    eps = pd.Series([px.asof(d) / (base_pe * rng.uniform(0.75, 1.3)) if d >= px.index[0]
                     else px.iloc[0] / base_pe for d in years], index=years)
    bvps = eps * rng.uniform(4, 10)
    info = {"longName": f"{symbol} (demo)", "sector": "Demo", "trailingPE": float(px.iloc[-1] / eps.iloc[-1]),
            "priceToBook": float(px.iloc[-1] / bvps.iloc[-1]), "returnOnEquity": float(rng.uniform(0.05, 0.3)),
            "debtToEquity": float(rng.uniform(0, 150)), "profitMargins": float(rng.uniform(0.03, 0.25)),
            "marketCap": float(rng.uniform(5e11, 2e13))}
    return {"info": info, "eps": eps, "bvps": bvps}
