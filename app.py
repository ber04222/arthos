"""Arthos - NSE market intelligence.

Scanner, pattern finder, trade-plan mapper, valuation bands and Claude analysis.
Run:  streamlit run app.py
"""
from __future__ import annotations

import time
from collections import Counter

import pandas as pd
import streamlit as st

import ai
import charts
from charts import ACCENT, DOWN, FAINT, INK, MUTED, UP
from data import NIFTY50, NIFTY_ETF, PERIODS, get_fundamentals, get_history, get_index_quote, get_many, to_symbol
from strategy import analyze
from valuation import valuation

st.set_page_config(page_title="Arthos", page_icon="◆", layout="wide", initial_sidebar_state="expanded")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame, button, input {{ font-family: 'Inter', sans-serif; }}
.block-container {{ padding: 1.6rem 2.2rem 3rem; max-width: 1400px; }}
#MainMenu, footer, [data-testid="stDeployButton"], [data-testid="stToolbar"] {{ visibility: hidden; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid #E5E7EB; }}
h1, h2, h3, h4 {{ color: {INK}; letter-spacing: -0.01em; }}

/* metrics as cards */
[data-testid="stMetric"] {{ background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; padding: 14px 16px; }}
[data-testid="stMetricLabel"] p {{ font-size: 11px !important; text-transform: uppercase; letter-spacing: .06em;
                                   color: {MUTED} !important; font-weight: 500; }}
[data-testid="stMetricValue"] {{ font-size: 1.45rem !important; font-weight: 600; color: {INK};
                                font-variant-numeric: tabular-nums; }}

/* bordered containers */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{ background: #FFFFFF; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 12px !important; border-color: #E5E7EB !important; }}

/* tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid #E5E7EB; }}
.stTabs [data-baseweb="tab"] {{ padding: 0.6rem 0; font-weight: 500; color: {MUTED}; }}
.stTabs [aria-selected="true"] {{ color: {INK} !important; }}

.brand {{ display:flex; align-items:center; gap:10px; }}
.brand .mark {{ width:30px; height:30px; border-radius:8px; background:{ACCENT}; color:white; display:grid;
               place-items:center; font-size:15px; font-weight:700; }}
.brand .name {{ font-size:1.5rem; font-weight:700; color:{INK}; letter-spacing:-0.02em; }}
.brand .tag {{ color:{FAINT}; font-size:.85rem; margin-left:4px; }}
.pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600; }}
.pill.up {{ background:rgba(22,163,74,.1); color:{UP}; }}
.pill.down {{ background:rgba(220,38,38,.1); color:{DOWN}; }}
.pill.neutral {{ background:#F1F5F9; color:{MUTED}; }}
.mkt {{ text-align:right; color:{MUTED}; font-size:.8rem; line-height:1.5; }}
.mkt b {{ color:{INK}; font-size:1.05rem; font-variant-numeric: tabular-nums; }}
.section {{ font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; color:{FAINT}; font-weight:600;
            margin: .2rem 0 .4rem; }}
.sig {{ display:flex; gap:10px; padding:9px 0; border-bottom:1px solid #F1F5F9; }}
.sig:last-child {{ border-bottom:none; }}
.sig .dot {{ width:8px; height:8px; border-radius:50%; margin-top:6px; flex:none; }}
.sig .t {{ color:{INK}; font-weight:500; font-size:.9rem; }}
.sig .d {{ color:{FAINT}; font-size:.78rem; }}
.verdict {{ font-size:1.05rem; font-weight:600; }}
.note {{ background:#F1F5F9; color:{MUTED}; border-radius:8px; padding:8px 12px; font-size:.82rem; margin-bottom:12px; }}
.plan td, .plan th {{ padding:7px 4px; font-size:.88rem; border:none; font-variant-numeric: tabular-nums; }}
.plan th {{ color:{FAINT}; font-weight:500; font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; text-align:left; }}
.plan table {{ width:100%; border-collapse:collapse; }}
.plan tr {{ border-bottom:1px solid #F1F5F9; }}
</style>""", unsafe_allow_html=True)

CHART_CFG = {"displayModeBar": False}


# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("<div class='brand'><div class='mark'>◆</div><div class='name'>Arthos</div></div>",
                unsafe_allow_html=True)
    st.write("")
    st.markdown("<div class='section'>Data</div>", unsafe_allow_html=True)
    demo = st.toggle("Demo data (offline)", value=False, help="Synthetic prices for when Yahoo Finance is unreachable.")
    st.markdown("<div class='section'>Chart</div>", unsafe_allow_html=True)
    emas = st.pills("Moving averages", [9, 21, 50, 200], default=[21, 50], selection_mode="multi",
                    format_func=lambda n: f"EMA {n}") or []
    show_plan = st.checkbox("Show trade plan on chart", value=True)
    st.markdown("<div class='section'>Ask AI</div>", unsafe_allow_html=True)
    api_key = st.text_input("Anthropic API key", type="password", placeholder="sk-ant-…",
                            help="Or set ANTHROPIC_API_KEY in your environment.", label_visibility="collapsed")
    st.caption(f"Model · `{ai.MODEL}`")
    st.write("")
    st.caption("Educational tool, not investment advice. Prices via Yahoo Finance, delayed ~15 min.")

for k, v in (("symbol", "RELIANCE"), ("chat", {}), ("pending_q", None)):
    st.session_state.setdefault(k, v)


def fmt(x: float, d: int = 2) -> str:
    return f"₹{x:,.{d}f}"


def pill(text: str, kind: str) -> str:
    return f"<span class='pill {kind}'>{text}</span>"


def load(symbol: str, period: str) -> pd.DataFrame:
    df = get_history(to_symbol(symbol), period, demo)
    if df.empty:
        st.error(f"Couldn't load **{symbol}** from Yahoo Finance. Check the ticker or your connection, "
                 "or turn on Demo data in the sidebar.")
        st.stop()
    return df


# ----------------------------------------------------------------- header
h1, h2 = st.columns([3, 1.2])
with h1:
    st.markdown("<div class='brand'><div class='mark'>◆</div><div class='name'>Arthos</div>"
                "<div class='tag'>NSE market intelligence</div></div>", unsafe_allow_html=True)
with h2:
    q = get_index_quote(demo)
    if q:
        kind = "up" if q["change"] >= 0 else "down"
        pct_txt = f"{q['pct']:+.2f}%"
        st.markdown(f"<div class='mkt'>NIFTY 50 &nbsp;<b>{q['price']:,.2f}</b> &nbsp;"
                    f"{pill(pct_txt, kind)}<br>as of {q['date']:%d %b %Y}</div>", unsafe_allow_html=True)
if demo:
    st.markdown("<div class='note'>Demo mode: prices and fundamentals are synthetic, not real market data.</div>",
                unsafe_allow_html=True)

tab_scan, tab_chart, tab_val, tab_ai, tab_port = st.tabs(["Scan", "Analysis", "Valuation", "Ask AI", "Portfolio"])


# ----------------------------------------------------------------- scan
def signal_family(name: str) -> str:
    if name in ("Breakout", "Breakdown"):
        return name
    if "cross" in name:
        return "MA crossover"
    if "RSI" in name:
        return "RSI"
    return "Candlestick"


def run_scan(symbols: list[str]) -> tuple[pd.DataFrame, Counter]:
    steps = ["Scanning market", "Identifying patterns", "Finding opportunities", "Tracking breakouts",
             "Mapping entry & exit points"]
    status = st.status(steps[0] + "…", expanded=False)
    data = get_many(tuple(to_symbol(s) for s in symbols), "1y", demo)
    if not data:
        status.update(label="No data returned - Yahoo may be unreachable. Try Demo data.", state="error")
        return pd.DataFrame(), Counter()
    rows, fams = [], Counter()
    for i, (sym, df) in enumerate(data.items()):
        status.update(label=steps[1 + int(3 * i / len(data))] + "…")
        r = analyze(df)
        recent = [s for s in r["signals"] if (r["df"].index[-1] - s["date"]).days <= 10]
        fams.update(signal_family(s["name"]) for s in recent if s["type"] != "neutral")
        names = list(dict.fromkeys(s["name"] for s in recent if s["type"] != "neutral"))
        p, sc, last = r["plan"], r["score"], r["df"].iloc[-1]
        hi52, lo52 = df["High"].iloc[-252:].max(), df["Low"].iloc[-252:].min()
        rows.append({
            "Symbol": sym.replace(".NS", ""), "Score": sc["score"], "Bias": p["direction"],
            "Price": float(last.Close), "Chg %": 100 * (df.Close.iloc[-1] / df.Close.iloc[-2] - 1),
            "3M %": sc["ret_3m"], "RSI": sc["rsi"],
            "52W": 100 * (last.Close - lo52) / (hi52 - lo52) if hi52 > lo52 else 50,
            "Vol x": float(last.Volume / last.VolSMA20) if last.VolSMA20 else 1.0,
            "Signals": (", ".join(names[:2]) + (f"  +{len(names) - 2}" if len(names) > 2 else "")) or "—",
            "Breakout": any(s["name"] == "Breakout" for s in recent),
            "Entry": p["entry"], "Stop": p["stop"], "Target": p["t2"], "R:R": p["rr"],
        })
    status.update(label=f"{steps[-1]} ✓  ·  {len(rows)} stocks analysed", state="complete")
    return pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True), fams


with tab_scan:
    st.write("")
    c0, c1, c2 = st.columns([4, 1.3, 1])
    c0.markdown(f"<div style='color:{MUTED};padding-top:8px'>Rank stocks by trend, momentum, volume and fresh "
                "patterns, with an entry, stop and target for each.</div>", unsafe_allow_html=True)
    with c1.popover(f"Universe · {len(st.session_state.get('universe', NIFTY50))}", use_container_width=True):
        universe = st.multiselect("Stocks to scan", NIFTY50, default=NIFTY50, key="universe")
    if c2.button("Run scan", type="primary", use_container_width=True):
        st.session_state.scan, st.session_state.fams = run_scan(universe)

    res = st.session_state.get("scan")
    if res is None or res.empty:
        st.markdown("<div class='note'>Run a scan to rank the Nifty 50 by trend, momentum, volume and "
                    "fresh patterns, with entry, stop and target for each stock.</div>", unsafe_allow_html=True)
    else:
        m = st.columns(4)
        m[0].metric("Stocks scanned", len(res))
        m[1].metric("Breakouts (10d)", int(res.Breakout.sum()))
        m[2].metric("Long / Short", f"{int((res.Bias == 'LONG').sum())} / {int((res.Bias == 'SHORT').sum())}")
        m[3].metric("Top pick", res.iloc[0].Symbol, f"score {res.iloc[0].Score}", delta_color="off", delta_arrow="off")

        g1, g2 = st.columns([2, 1])
        with g1, st.container(border=True):
            st.markdown("<div class='section'>Opportunity map</div>", unsafe_allow_html=True)
            st.plotly_chart(charts.opportunity_map(res), use_container_width=True, config=CHART_CFG)
        with g2, st.container(border=True):
            st.markdown("<div class='section'>Signals in last 10 days</div>", unsafe_allow_html=True)
            fams = st.session_state.get("fams") or Counter()
            if fams:
                st.plotly_chart(charts.signal_mix(pd.Series(fams)), use_container_width=True, config=CHART_CFG)
            else:
                st.caption("No directional signals.")

        f1, f2, f3, _ = st.columns([1, 1.4, 1, 2])
        bias = f1.segmented_control("Bias", ["All", "LONG", "SHORT"], default="All", label_visibility="collapsed")
        min_score = f2.slider("Min score", 0, 100, 0, label_visibility="collapsed", format="Score ≥ %d")
        only_bo = f3.toggle("Breakouts only")
        view = res[res.Score >= min_score]
        if bias and bias != "All":
            view = view[view.Bias == bias]
        if only_bo:
            view = view[view.Breakout]
        view = view.drop(columns=["Breakout", "Vol x"]).reset_index(drop=True)

        styled = (view.style
                  .map(lambda v: f"color:{UP};font-weight:600" if v == "LONG" else f"color:{DOWN};font-weight:600",
                       subset=["Bias"])
                  .map(lambda v: f"color:{UP}" if v > 0 else f"color:{DOWN}" if v < 0 else "", subset=["Chg %", "3M %"]))
        sel = st.dataframe(
            styled, hide_index=True, use_container_width=True, height=min(38 * len(view) + 40, 560),
            on_select="rerun", selection_mode="single-row",
            column_config={
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d", width="small"),
                "Price": st.column_config.NumberColumn(format="₹%.2f"),
                "Chg %": st.column_config.NumberColumn(format="%+.2f%%", width="small"),
                "3M %": st.column_config.NumberColumn(format="%+.1f%%", width="small"),
                "RSI": st.column_config.NumberColumn(format="%.0f", width="small"),
                "52W": st.column_config.ProgressColumn("52W range", min_value=0, max_value=100, format=" ",
                                                       help="Where price sits between the 52-week low and high"),
                "Entry": st.column_config.NumberColumn(format="%.2f"),
                "Stop": st.column_config.NumberColumn(format="%.2f"),
                "Target": st.column_config.NumberColumn(format="%.2f"),
                "R:R": st.column_config.NumberColumn(format="%.1f", width="small"),
            })
        if sel and sel.selection.rows:
            st.session_state.symbol = view.iloc[sel.selection.rows[0]]["Symbol"]
            st.caption(f"Selected **{st.session_state.symbol}** · open the Analysis tab for the full chart.")


# ----------------------------------------------------------------- analysis
with tab_chart:
    st.write("")
    c1, c2, c3 = st.columns([2, 2, 2])
    options = sorted(set(NIFTY50) | {st.session_state.symbol})
    symbol = c1.selectbox("Stock", options, index=options.index(st.session_state.symbol),
                          label_visibility="collapsed")
    custom = c2.text_input("Ticker", placeholder="Any NSE ticker, e.g. IRFC", label_visibility="collapsed")
    if custom:
        symbol = custom.strip().upper()
    st.session_state.symbol = symbol
    rng = c3.segmented_control("Range", list(PERIODS), default="1Y", label_visibility="collapsed") or "1Y"

    full = load(symbol, "2y" if rng in ("6M", "1Y") else PERIODS[rng])
    result = analyze(full)
    st.session_state.result = result
    disp = {"6M": 126, "1Y": 252, "3Y": 756, "5Y": 1260}[rng]
    shown = dict(result, df=result["df"].iloc[-disp:])
    df, p, sc = result["df"], result["plan"], result["score"]
    last, prev = df.iloc[-1], df.iloc[-2]
    chg = 100 * (last.Close / prev.Close - 1)

    k = st.columns(5)
    k[0].metric(symbol, fmt(last.Close), f"{chg:+.2f}%")
    k[1].metric("Score", f"{sc['score']} / 100")
    k[2].metric("Bias", p["direction"].title())
    k[3].metric("RSI 14", f"{last.RSI:.0f}",
                "overbought" if last.RSI > 70 else "oversold" if last.RSI < 30 else "neutral", delta_color="off",
                delta_arrow="off")
    k[4].metric("3M return", f"{sc['ret_3m']:+.1f}%")

    with st.container(border=True):
        st.plotly_chart(charts.price_chart(shown, tuple(sorted(emas)), show_plan), use_container_width=True,
                        config=CHART_CFG)

    left, mid, right = st.columns([1.15, 1, 1])
    with left, st.container(border=True):
        st.markdown("<div class='section'>Trade plan</div>", unsafe_allow_html=True)
        rows = "".join(
            f"<tr><td>{lbl}</td><td style='color:{col};font-weight:600'>{fmt(p[key])}</td>"
            f"<td style='color:{FAINT}'>{100 * (p[key] / p['entry'] - 1):+.1f}%</td></tr>"
            for lbl, key, col in (("Entry", "entry", INK), ("Stop loss", "stop", DOWN),
                                  ("Target 1", "t1", UP), ("Target 2", "t2", UP)))
        st.markdown(f"<div class='plan'><table><tr><th>Level</th><th>Price</th><th>From entry</th></tr>{rows}"
                    f"</table></div>", unsafe_allow_html=True)
        st.markdown(f"{pill(p['direction'], 'up' if p['direction'] == 'LONG' else 'down')} &nbsp;"
                    f"<span style='color:{MUTED};font-size:.85rem'>Risk {p['risk_pct']}% · Reward:Risk "
                    f"<b style='color:{INK}'>{p['rr']}</b></span>", unsafe_allow_html=True)
    with mid, st.container(border=True):
        st.markdown("<div class='section'>Score breakdown</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.score_bars(sc), use_container_width=True, config=CHART_CFG)
    with right, st.container(border=True, height=286):
        st.markdown("<div class='section'>Recent signals</div>", unsafe_allow_html=True)
        sigs = result["signals"][:8]
        if not sigs:
            st.caption("No recent patterns.")
        html = ""
        for s in sigs:
            col = {"bullish": UP, "bearish": DOWN}.get(s["type"], FAINT)
            html += (f"<div class='sig'><div class='dot' style='background:{col}'></div><div>"
                     f"<div class='t'>{s['name']}</div><div class='d'>{s['date']:%d %b} · {s['detail']}</div></div></div>")
        st.markdown(html, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("<div class='section'>Price vs key levels</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.level_ladder(float(last.Close), p, result["levels"]), use_container_width=True,
                        config=CHART_CFG)


# ----------------------------------------------------------------- valuation
with tab_val:
    st.write("")
    sym = st.session_state.symbol
    hist5 = load(sym, "5y")
    fund = get_fundamentals(to_symbol(sym), demo)
    val = valuation(hist5["Close"], fund)
    st.session_state.val = val

    cols = st.columns(2)
    for col, key, label in ((cols[0], "pe", "P/E"), (cols[1], "pb", "P/B")):
        with col, st.container(border=True):
            b = val[key]
            st.markdown(f"<div class='section'>{sym} · {label} ratio</div>", unsafe_allow_html=True)
            if b is None:
                fb = val["trailing_pe"] if key == "pe" else val["price_to_book"]
                st.caption(f"Not enough history for a {label} band." + (f" Current {label}: **{fb:.2f}**" if fb else ""))
                continue
            vcol = {"Undervalued": UP, "Overvalued": DOWN}.get(b["verdict"], ACCENT)
            st.markdown(f"<span class='verdict' style='color:{vcol}'>{b['verdict']}</span> "
                        f"<span style='color:{MUTED};font-size:.85rem'>· {label} is at the "
                        f"{b['percentile']:.0f}th percentile of its history</span>", unsafe_allow_html=True)
            st.plotly_chart(charts.percentile_gauge(b["percentile"]), use_container_width=True, config=CHART_CFG,
                            key=f"gauge_{key}")
            m = st.columns(3)
            m[0].metric("Current", f"{b['current']:.1f}")
            m[1].metric("Median", f"{b['median']:.1f}")
            m[2].metric("Low / High", f"{b['min']:.0f} / {b['max']:.0f}")
            st.plotly_chart(charts.band_chart(b, label), use_container_width=True, config=CHART_CFG, key=f"band_{key}")
            st.caption(f"Buy zone below {b['buy_below']:.1f} (20th pct) · Sell zone above {b['sell_above']:.1f} "
                       f"(80th pct) · Volatility {b['volatility']:.0f}%")

    info = val["info"]
    if info:
        st.markdown("<div class='section'>Fundamentals</div>", unsafe_allow_html=True)
        mc = info.get("marketCap")
        f = st.columns(5)
        f[0].metric("Sector", info.get("sector", "—"))
        f[1].metric("Market cap", (f"₹{mc / 1e12:,.2f} L Cr" if mc >= 1e12 else f"₹{mc / 1e7:,.0f} Cr") if mc else "—")
        f[2].metric("ROE", f"{100 * info['returnOnEquity']:.1f}%" if info.get("returnOnEquity") else "—")
        f[3].metric("Debt / Equity", f"{info['debtToEquity'] / 100:.2f}" if info.get("debtToEquity") is not None else "—")
        f[4].metric("Net margin", f"{100 * info['profitMargins']:.1f}%" if info.get("profitMargins") else "—")


# ----------------------------------------------------------------- ask ai
SUGGESTIONS = {
    "Full analysis": "Give me your full analysis and trade plan for this stock.",
    "Good entry now?": "Is this a good entry right now? What would make you wait?",
    "Key risks": "What are the key risks to this setup, technical and fundamental?",
    "Swing vs positional": "Is this better as a 2-week swing trade or a 6-month positional trade?",
}

with tab_ai:
    st.write("")
    sym = st.session_state.symbol
    client = ai.get_client(api_key)
    st.markdown(f"#### Ask about {sym}")
    if client is None:
        st.markdown("<div class='note'>Add your Anthropic API key in the sidebar (or set "
                    "<code>ANTHROPIC_API_KEY</code>) to chat with Claude about this stock.</div>",
                    unsafe_allow_html=True)
    else:
        context = ai.build_context(sym, st.session_state.result, st.session_state.get("val"))
        history = st.session_state.chat.setdefault(sym, [])
        choice = st.pills("Suggestions", list(SUGGESTIONS), label_visibility="collapsed", key=f"sugg_{len(history)}")
        if choice:
            history.append({"role": "user", "content": SUGGESTIONS[choice]})

        for m in history:
            with st.chat_message(m["role"], avatar="◆" if m["role"] == "assistant" else None):
                st.markdown(m["content"])

        q = st.chat_input(f"Ask anything about {sym}")
        if q:
            history.append({"role": "user", "content": q})
            with st.chat_message("user"):
                st.markdown(q)

        if history and history[-1]["role"] == "user":
            with st.chat_message("assistant", avatar="◆"):
                try:
                    reply = st.write_stream(ai.stream_chat(client, context, history))
                    history.append({"role": "assistant", "content": reply})
                except Exception as e:  # auth / rate limit / network
                    history.pop()
                    st.error(f"Claude API error: {e}")
        if history and st.button("Clear conversation", type="tertiary"):
            history.clear()
            st.rerun()
        with st.expander("Data sent to Claude"):
            st.code(context, language="json")


# ----------------------------------------------------------------- portfolio
with tab_port:
    st.write("")
    res = st.session_state.get("scan")
    if res is None or res.empty:
        st.markdown("<div class='note'>Run a scan first. The portfolio is built from the scan results.</div>",
                    unsafe_allow_html=True)
    else:
        with st.container(border=True):
            st.markdown("<div class='section'>Allocation</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            w_mom = c1.slider("Momentum %", 0, 100, 50, 5)
            w_idx = c2.slider("Nifty 50 ETF %", 0, 100 - w_mom, min(25, 100 - w_mom), 5)
            w_q = 100 - w_mom - w_idx
            n = c3.number_input("Stocks per bucket", 2, 10, 5)
            capital = c4.number_input("Capital (₹)", 10_000, 100_000_000, 500_000, 10_000)
            st.caption(f"Quality gets the remaining **{w_q}%**. Momentum = strongest 3-month returns among long "
                       "setups. Quality = high score with RSI 40–65 (steady uptrend, not stretched).")

        longs = res[res.Bias == "LONG"]
        momentum = longs.sort_values(["3M %", "Score"], ascending=False).head(int(n))
        quality = longs[~longs.Symbol.isin(momentum.Symbol) & longs.RSI.between(40, 65)] \
            .sort_values("Score", ascending=False).head(int(n))

        alloc = []
        for bucket, frame, w in (("Momentum", momentum, w_mom), ("Quality", quality, w_q)):
            for _, row in frame.iterrows():
                alloc.append({"Bucket": bucket, "Holding": row.Symbol, "Weight": w / max(1, len(frame)),
                              "Price": row.Price, "Score": row.Score})
        if w_idx:
            alloc.append({"Bucket": "Nifty 50", "Holding": NIFTY_ETF.replace(".NS", ""), "Weight": float(w_idx),
                          "Price": float("nan"), "Score": float("nan")})
        a = pd.DataFrame(alloc)
        if a.empty:
            st.warning("No long setups in the scan to build a portfolio from.")
        else:
            a["Amount"] = a["Weight"] / 100 * capital
            a["Qty"] = [amt // px if pd.notna(px) and px else float("nan") for amt, px in zip(a.Amount, a.Price)]
            left, right = st.columns([1, 1.8])
            with left, st.container(border=True):
                st.markdown("<div class='section'>By strategy</div>", unsafe_allow_html=True)
                buckets = a.groupby("Bucket", sort=False)["Weight"].sum()
                st.plotly_chart(charts.allocation_donut(buckets, capital), use_container_width=True, config=CHART_CFG)
            with right, st.container(border=True):
                st.markdown("<div class='section'>Holdings</div>", unsafe_allow_html=True)
                st.dataframe(a, hide_index=True, use_container_width=True, height=min(36 * len(a) + 40, 420),
                             column_config={
                                 "Weight": st.column_config.ProgressColumn("Weight", min_value=0,
                                                                           max_value=float(a.Weight.max()), format="%.1f%%"),
                                 "Price": st.column_config.NumberColumn(format="₹%.2f"),
                                 "Amount": st.column_config.NumberColumn(format="₹%.0f"),
                                 "Score": st.column_config.NumberColumn(format="%d"),
                                 "Qty": st.column_config.NumberColumn(format="%d"),
                             })
