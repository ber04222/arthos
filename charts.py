"""Plotly figures for Arthos, all sharing one light, minimal style."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from theme import ACCENT, ACCENT2, ACCENT_SOFT, BORDER, DOWN, FAINT, GRID, INK, MUTED, UP, rgba

UP_SOFT = rgba(UP, 0.08)
DOWN_SOFT = rgba(DOWN, 0.08)
FONT = "Inter, -apple-system, Segoe UI, sans-serif"
SCALE = [[0, ACCENT_SOFT], [1, ACCENT]]

EMA_COLORS = {9: "#F59E0B", 21: ACCENT, 50: ACCENT2, 200: "#A1A1AA"}


def base_layout(fig: go.Figure, height: int, **kw) -> go.Figure:
    fig.update_layout(
        height=height, template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=MUTED), margin=dict(l=8, r=8, t=8, b=8),
        dragmode=False,  # let touch gestures scroll the page on phones
        hoverlabel=dict(bgcolor="white", bordercolor=BORDER, font=dict(family=FONT, color=INK, size=12)),
        legend=dict(orientation="h", x=0, y=1.04, yanchor="bottom", font=dict(size=11, color=MUTED),
                    bgcolor="rgba(0,0,0,0)"),
        **kw,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=BORDER, tickfont=dict(color=FAINT),
                     showspikes=True, spikecolor=FAINT, spikethickness=1, spikedash="dot", spikemode="across")
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, tickfont=dict(color=FAINT), side="right")
    return fig


# ------------------------------------------------------------------ price
def price_chart(r: dict, emas: tuple[int, ...] = (21, 50), show_plan: bool = True) -> go.Figure:
    df, plan, lv = r["df"], r["plan"], r["levels"]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.04,
                        specs=[[{"secondary_y": True}], [{}]])

    # volume as a faint overlay on the bottom of the price panel
    vcol = [rgba(UP, 0.25) if c >= o else rgba(DOWN, 0.25)
            for o, c in zip(df.Open, df.Close)]
    fig.add_trace(go.Bar(x=df.index, y=df.Volume, marker_color=vcol, marker_line_width=0, name="Volume",
                         showlegend=False, hovertemplate="Vol %{y:,.0f}<extra></extra>"), 1, 1, secondary_y=True)

    fig.add_trace(go.Candlestick(
        x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="Price",
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
        decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN), showlegend=False), 1, 1)

    for n in emas:
        fig.add_trace(go.Scatter(x=df.index, y=df[f"EMA{n}"], name=f"EMA {n}", mode="lines",
                                 line=dict(width=1.4, color=EMA_COLORS[n]),
                                 hovertemplate=f"EMA {n} " + "%{y:,.2f}<extra></extra>"), 1, 1)

    for s in lv["support"][:2]:
        fig.add_hline(y=s, line=dict(color=UP, width=1, dash="dot"), opacity=0.45, row=1, col=1)
    for s in lv["resistance"][:2]:
        fig.add_hline(y=s, line=dict(color=DOWN, width=1, dash="dot"), opacity=0.45, row=1, col=1)

    # recent pattern markers only
    cutoff = df.index[-1] - pd.Timedelta(days=30)
    marks = [s for s in r["signals"] if s["date"] >= cutoff and s["type"] != "neutral" and s["date"] in df.index]
    for kind, sym, col, ypos, k in (("bullish", "triangle-up", UP, "Low", 0.985),
                                    ("bearish", "triangle-down", DOWN, "High", 1.015)):
        ms = [s for s in marks if s["type"] == kind]
        if ms:
            fig.add_trace(go.Scatter(
                x=[s["date"] for s in ms], y=[df.loc[s["date"], ypos] * k for s in ms], mode="markers",
                marker=dict(symbol=sym, size=9, color=col, line=dict(width=0)), showlegend=False,
                hovertemplate="%{text}<extra></extra>", text=[s["name"] for s in ms]), 1, 1)

    if show_plan:
        x0 = df.index[-min(20, len(df))]
        x1 = df.index[-1] + pd.Timedelta(days=10)
        reward_hi = max(plan["t2"], plan["entry"])
        reward_lo = min(plan["t2"], plan["entry"])
        risk_hi = max(plan["stop"], plan["entry"])
        risk_lo = min(plan["stop"], plan["entry"])
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=reward_lo, y1=reward_hi, fillcolor=UP_SOFT, line_width=0,
                      layer="below", row=1, col=1)
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=risk_lo, y1=risk_hi, fillcolor=DOWN_SOFT, line_width=0,
                      layer="below", row=1, col=1)
        for key, col, lbl in (("entry", INK, "Entry"), ("stop", DOWN, "Stop"), ("t1", UP, "T1"), ("t2", UP, "T2")):
            fig.add_shape(type="line", x0=x0, x1=x1, y0=plan[key], y1=plan[key],
                          line=dict(color=col, width=1, dash="solid" if key == "entry" else "dash"), row=1, col=1)
            fig.add_annotation(x=x1, y=plan[key], text=f"<b>{lbl}</b> {plan[key]:,.0f}", showarrow=False,
                               xanchor="left", xshift=4, font=dict(color="white", size=10),
                               bgcolor=col, borderpad=3, row=1, col=1)

    # RSI panel
    fig.add_hrect(y0=30, y1=70, fillcolor=rgba(ACCENT, 0.05), line_width=0, row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.RSI, mode="lines", line=dict(color=ACCENT, width=1.3),
                             name="RSI", showlegend=False, hovertemplate="RSI %{y:.0f}<extra></extra>"), 2, 1)

    base_layout(fig, 560, hovermode="x unified", xaxis_rangeslider_visible=False)
    fig.update_layout(margin=dict(l=8, r=80, t=28, b=8))
    vmax = float(df.Volume.max()) if len(df) else 1
    fig.update_yaxes(secondary_y=True, range=[0, vmax * 4], showgrid=False, showticklabels=False, row=1, col=1)
    fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], row=2, col=1)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.add_annotation(text="RSI 14", xref="paper", yref="paper", x=0, y=0.2, showarrow=False,
                       font=dict(size=10, color=FAINT), xanchor="left")
    return fig


# ------------------------------------------------------------------ levels ladder
def level_ladder(price: float, plan: dict, levels: dict) -> go.Figure:
    pts = ([("Support", s, UP) for s in levels["support"][:3]] +
           [("Resistance", s, DOWN) for s in levels["resistance"][:3]] +
           [("Stop", plan["stop"], DOWN), ("Target 1", plan["t1"], UP), ("Target 2", plan["t2"], UP)])
    pts.append(("Price", price, INK))
    pts.sort(key=lambda p: p[1])
    fig = go.Figure()
    lo, hi = pts[0][1], pts[-1][1]
    fig.add_shape(type="line", x0=lo, x1=hi, y0=0, y1=0, line=dict(color=BORDER, width=2))
    for i, (name, v, col) in enumerate(pts):
        is_px = name == "Price"
        fig.add_trace(go.Scatter(
            x=[v], y=[0], mode="markers", showlegend=False,
            marker=dict(size=14 if is_px else 9, color=col, symbol="diamond" if is_px else "circle",
                        line=dict(color="white", width=2)),
            hovertemplate=f"{name}: ₹{v:,.2f} ({100 * (v / price - 1):+.1f}%)<extra></extra>"))
        fig.add_annotation(x=v, y=0, text=f"{name}<br><b>{v:,.0f}</b>", showarrow=False,
                           yshift=26 if i % 2 == 0 else -28, font=dict(size=10, color=col if not is_px else INK))
    base_layout(fig, 150)
    fig.update_xaxes(visible=False, showspikes=False, range=[lo - (hi - lo) * 0.06, hi + (hi - lo) * 0.06])
    fig.update_yaxes(visible=False, range=[-1, 1])
    return fig


# ------------------------------------------------------------------ score
def score_bars(score: dict) -> go.Figure:
    items = [("Trend", score["trend"], 35), ("Momentum", score["momentum"], 35),
             ("Volume", score["volume"], 15), ("Pattern", score["pattern"], 15)]
    names = [i[0] for i in items][::-1]
    vals = [max(0, i[1]) for i in items][::-1]
    maxes = [i[2] for i in items][::-1]
    pct = [100 * v / m for v, m in zip(vals, maxes)]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=names, x=[100] * 4, orientation="h", marker_color=GRID, hoverinfo="skip", width=0.42))
    fig.add_trace(go.Bar(y=names, x=pct, orientation="h", marker=dict(color=pct, colorscale=SCALE, cmin=0, cmax=100), width=0.42,
                         hoverinfo="skip"))
    for n, v, m in zip(names, vals, maxes):
        fig.add_annotation(x=100, y=n, text=f"{v:.0f}<span style='color:{FAINT}'>/{m}</span>", showarrow=False,
                           xanchor="left", xshift=8, font=dict(size=11, color=INK))
    base_layout(fig, 190, barmode="overlay", showlegend=False)
    fig.update_layout(margin=dict(l=8, r=48, t=8, b=8))
    fig.update_xaxes(visible=False, showspikes=False, range=[0, 100])
    fig.update_yaxes(showgrid=False, side="left", tickfont=dict(color=INK, size=12))
    return fig


# ------------------------------------------------------------------ valuation
def band_chart(b: dict, label: str) -> go.Figure:
    s = b["series"]
    lo_edge = min(b["min"], s.min()) * 0.92
    hi_edge = max(b["max"], s.max()) * 1.06
    fig = go.Figure()
    fig.add_hrect(y0=b["sell_above"], y1=hi_edge, fillcolor=DOWN_SOFT, line_width=0)
    fig.add_hrect(y0=lo_edge, y1=b["buy_below"], fillcolor=UP_SOFT, line_width=0)
    fig.add_annotation(text="Sell zone", xref="paper", x=0.01, y=hi_edge, yanchor="top", showarrow=False,
                       font=dict(size=10, color=DOWN))
    fig.add_annotation(text="Buy zone", xref="paper", x=0.01, y=lo_edge, yanchor="bottom", showarrow=False,
                       font=dict(size=10, color=UP))
    fig.add_hline(y=b["median"], line=dict(color=FAINT, width=1, dash="dot"),
                  annotation_text=f"median {b['median']:.1f}", annotation_position="right",
                  annotation_font=dict(size=10, color=FAINT))
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color=ACCENT, width=1.6),
                             hovertemplate=f"{label} " + "%{y:.2f}<extra></extra>", showlegend=False))
    fig.add_trace(go.Scatter(x=[s.index[-1]], y=[s.iloc[-1]], mode="markers", showlegend=False,
                             marker=dict(size=9, color=ACCENT, line=dict(color="white", width=2)), hoverinfo="skip"))
    base_layout(fig, 280, hovermode="x unified")
    fig.update_yaxes(range=[lo_edge, hi_edge])
    fig.update_layout(margin=dict(l=8, r=60, t=8, b=8))
    return fig


def percentile_gauge(pct: float) -> go.Figure:
    col = UP if pct < 20 else DOWN if pct > 80 else ACCENT
    fig = go.Figure(go.Indicator(
        mode="gauge", value=pct,
        gauge=dict(shape="bullet", axis=dict(range=[0, 100], tickvals=[0, 20, 50, 80, 100],
                                             tickfont=dict(size=10, color=FAINT)),
                   bar=dict(color="rgba(0,0,0,0)", thickness=0), bgcolor="white", borderwidth=0,
                   threshold=dict(line=dict(color=col, width=4), thickness=0.9, value=pct),
                   steps=[dict(range=[0, 20], color=UP_SOFT), dict(range=[20, 80], color="#F8FAFC"),
                          dict(range=[80, 100], color=DOWN_SOFT)])))
    base_layout(fig, 70)
    fig.update_layout(margin=dict(l=8, r=8, t=6, b=22))
    return fig


# ------------------------------------------------------------------ scan overview
def opportunity_map(res: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for bias, col in (("LONG", UP), ("SHORT", DOWN)):
        d = res[res.Bias == bias]
        if d.empty:
            continue
        top = set(res.nlargest(4, "Score").Symbol) | set(res.nsmallest(2, "Score").Symbol)
        fig.add_trace(go.Scatter(
            x=d["3M %"], y=d["Score"], mode="markers+text", name=bias.title(),
            text=[s if s in top else "" for s in d["Symbol"]], hovertext=d["Symbol"],
            textposition="top center", textfont=dict(size=10, color=MUTED),
            marker=dict(size=(d["Vol x"].clip(0.5, 3) * 9), color=col, opacity=0.75, line=dict(color="white", width=1)),
            customdata=d[["Price", "RSI"]].values,
            hovertemplate="<b>%{hovertext}</b><br>Score %{y}<br>3M %{x:.1f}%<br>₹%{customdata[0]:,.2f} · RSI %{customdata[1]:.0f}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=BORDER, width=1))
    fig.add_hline(y=50, line=dict(color=BORDER, width=1))
    base_layout(fig, 330)
    fig.update_xaxes(title=dict(text="3-month return %", font=dict(size=11, color=FAINT)), ticksuffix="%",
                     showspikes=False)
    fig.update_yaxes(title=dict(text="Score", font=dict(size=11, color=FAINT)), side="left", range=[0, 105],
                     showspikes=False)
    fig.update_layout(margin=dict(l=8, r=8, t=28, b=8))
    return fig


def signal_mix(counts: pd.Series) -> go.Figure:
    counts = counts.sort_values()
    fig = go.Figure(go.Bar(y=counts.index, x=counts.values, orientation="h", marker=dict(color=counts.values, colorscale=SCALE, cmin=0, cmax=max(counts.max(), 1)), width=0.55,
                           text=counts.values, textposition="outside", textfont=dict(size=11, color=MUTED),
                           hovertemplate="%{y}: %{x}<extra></extra>"))
    base_layout(fig, 330, showlegend=False)
    fig.update_xaxes(visible=False, showspikes=False, range=[0, counts.max() * 1.25 if len(counts) else 1])
    fig.update_yaxes(showgrid=False, side="left", tickfont=dict(color=INK, size=11))
    return fig


# ------------------------------------------------------------------ portfolio
def allocation_donut(buckets: pd.Series, capital: float) -> go.Figure:
    palette = {"Momentum": ACCENT, "Quality": ACCENT2, "Nifty 50": "#CBD5E1"}
    fig = go.Figure(go.Pie(labels=buckets.index, values=buckets.values, hole=0.68, sort=False,
                           marker=dict(colors=[palette.get(b, FAINT) for b in buckets.index],
                                       line=dict(color="white", width=3)),
                           textinfo="none", hovertemplate="%{label}: %{value:.0f}%<extra></extra>"))
    fig.add_annotation(text="Capital", showarrow=False, x=0.5, y=0.58, font=dict(size=11, color=FAINT))
    fig.add_annotation(text=f"<b>₹{capital / 1e5:,.1f}L</b>", showarrow=False, x=0.5, y=0.47,
                       font=dict(size=22, color=INK))
    base_layout(fig, 300)
    fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05, yanchor="top"))
    return fig
