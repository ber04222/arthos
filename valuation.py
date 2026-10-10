"""Historical P/E and P/B bands with Buy/Sell zones."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ratio_series(price: pd.Series, per_share: pd.Series) -> pd.Series:
    """Step-align annual per-share figures to daily prices (last known value forward)."""
    if per_share is None or per_share.empty:
        return pd.Series(dtype=float)
    ps = per_share.copy()
    ps.index = pd.to_datetime(ps.index).tz_localize(None)
    ps = ps[ps > 0].sort_index()
    if ps.empty:
        return pd.Series(dtype=float)
    aligned = ps.reindex(price.index.union(ps.index)).ffill().reindex(price.index)
    # before the first report, back-fill with the earliest value
    aligned = aligned.bfill()
    return (price / aligned).dropna()


def band(series: pd.Series, current: float | None = None) -> dict | None:
    if series is None or len(series) < 20:
        return None
    cur = float(current if current is not None else series.iloc[-1])
    lo, hi = float(series.quantile(0.2)), float(series.quantile(0.8))
    verdict = "Undervalued" if cur < lo else "Overvalued" if cur > hi else "Fairly Valued"
    return {"series": series, "current": cur, "min": float(series.min()), "max": float(series.max()),
            "median": float(series.median()), "buy_below": lo, "sell_above": hi,
            "volatility": float(100 * series.std() / series.mean()), "verdict": verdict,
            "percentile": float((series < cur).mean() * 100)}


def valuation(price: pd.Series, fundamentals: dict) -> dict:
    info = fundamentals.get("info", {})
    pe = _ratio_series(price, fundamentals.get("eps"))
    pb = _ratio_series(price, fundamentals.get("bvps"))
    return {
        "pe": band(pe),
        "pb": band(pb),
        "trailing_pe": info.get("trailingPE"),
        "price_to_book": info.get("priceToBook"),
        "info": info,
    }
