"""
Trading 212 Browser Dashboard
==============================
A Streamlit web dashboard for your Trading 212 portfolio with
an interactive line chart of total portfolio value over time.

Requirements:
    pip install streamlit plotly pandas

Usage:
    streamlit run dashboard_web.py

Author: Teslim Adeyanju
"""

import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

from trading212_dashboard import (
    Trading212Client,
    PortfolioAnalytics,
    SnapshotManager,
    API_KEY,
    API_SECRET,
    BASE_URL,
    REFRESH_SECONDS,
)

st.set_page_config(
    page_title="Trading 212 Dashboard",
    page_icon="📈",
    layout="wide",
)

# ── Session state: accumulate value history across reruns ──
if "value_history" not in st.session_state:
    st.session_state.value_history = []
    snap = SnapshotManager()
    for row in snap.load_history(days=30):
        try:
            st.session_state.value_history.append(
                (datetime.fromisoformat(row["timestamp"]), float(row["total_value"]))
            )
        except (ValueError, KeyError):
            pass

# ── Fetch live data ──
client = Trading212Client(API_KEY, API_SECRET, BASE_URL)

st.title("📈 Trading 212 Portfolio")
st.caption(
    f"Auto-refreshes every {REFRESH_SECONDS}s  ·  "
    f"{datetime.now().strftime('%d %b %Y  %H:%M:%S')}"
)

with st.spinner("Fetching portfolio…"):
    summary = client.account_summary()
    positions_data = client.positions()

if not summary or positions_data is None:
    st.error("Could not connect to Trading 212 API — check your .env credentials.")
    time.sleep(REFRESH_SECONDS)
    st.rerun()

analytics = PortfolioAnalytics(summary, positions_data or [])
st.session_state.value_history.append((datetime.now(), analytics.total_value))
cur = analytics.currency

# ── KPI Cards ──
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Value", f"{cur}{analytics.total_value:,.2f}")
c2.metric("Invested", f"{cur}{analytics.invested:,.2f}")
c3.metric(
    "Total P&L",
    f"{cur}{analytics.total_pnl:+,.2f}",
    f"{analytics.total_pnl_pct:+.1f}%",
    delta_color="normal",
)
c4.metric("Cash", f"{cur}{analytics.cash:,.2f}")
c5.metric(
    "Win Rate",
    f"{analytics.win_rate:.0f}%",
    f"{len(analytics.winners)}W / {len(analytics.losers)}L",
    delta_color="off",
)

st.divider()

# ── Portfolio Value Line Chart ──
history = st.session_state.value_history
if len(history) >= 2:
    hist_ts, hist_vals = zip(*history)
    start_val = hist_vals[0]
    end_val = hist_vals[-1]
    is_up = end_val >= start_val
    line_color = "#22c55e" if is_up else "#ef4444"
    fill_color = "rgba(34,197,94,0.12)" if is_up else "rgba(239,68,68,0.12)"

    fig = go.Figure()

    # Shaded area + line
    fig.add_trace(
        go.Scatter(
            x=list(hist_ts),
            y=list(hist_vals),
            mode="lines",
            line=dict(color=line_color, width=2.5),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate=f"<b>{cur}%{{y:,.2f}}</b><br>%{{x}}<extra></extra>",
        )
    )

    # Dotted reference line at session start
    fig.add_hline(
        y=start_val,
        line_dash="dot",
        line_color="rgba(150,150,150,0.5)",
        annotation_text=f"Start  {cur}{start_val:,.2f}",
        annotation_position="bottom right",
        annotation_font_color="gray",
    )

    # Highlight current value with a marker
    fig.add_trace(
        go.Scatter(
            x=[hist_ts[-1]],
            y=[end_val],
            mode="markers",
            marker=dict(color=line_color, size=10, symbol="circle"),
            hovertemplate=f"<b>Now: {cur}{end_val:,.2f}</b><extra></extra>",
            showlegend=False,
        )
    )

    session_change = end_val - start_val
    session_pct = (session_change / start_val * 100) if start_val else 0
    arrow = "▲" if session_change >= 0 else "▼"

    fig.update_layout(
        title=dict(
            text=(
                f"Portfolio Value  "
                f"<span style='color:{line_color}'>"
                f"{arrow} {cur}{abs(session_change):,.2f} ({session_pct:+.1f}%)"
                f"</span>"
            ),
            font=dict(size=18),
        ),
        xaxis_title=None,
        yaxis=dict(tickprefix=cur, gridcolor="rgba(255,255,255,0.05)"),
        template="plotly_dark",
        height=400,
        margin=dict(l=0, r=0, t=50, b=0),
        showlegend=False,
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Accumulating data for the chart — check back after a few refreshes.")

st.divider()

# ── Positions Table ──
st.subheader("Positions")
rows = []
for p in sorted(analytics.positions, key=lambda x: x["_value"], reverse=True):
    ticker = p["_ticker"].replace("_US_EQ", "").replace("_EQ", "")
    rows.append(
        {
            "Ticker": ticker,
            "Value": p["_value"],
            "Cost": p["_cost"],
            "P&L": p["_pnl"],
            "Return %": p["_pnl_pct"],
            "Weight %": p["_weight"],
            "Currency": p["_currency"],
        }
    )

df = pd.DataFrame(rows)


def _colour_pnl(val):
    if isinstance(val, (int, float)):
        return "color: #22c55e" if val > 0 else ("color: #ef4444" if val < 0 else "")
    return ""


st.dataframe(
    df.style.format(
        {
            "Value": f"{cur}{{:,.2f}}",
            "Cost": f"{cur}{{:,.2f}}",
            "P&L": f"{cur}{{:+,.2f}}",
            "Return %": "{:+.1f}%",
            "Weight %": "{:.1f}%",
        }
    ).map(_colour_pnl, subset=["P&L", "Return %"]),
    use_container_width=True,
    hide_index=True,
)

# ── Sector & Currency side by side ──
st.divider()
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Sectors")
    sector_rows = []
    for sector, data in analytics.sector_breakdown.items():
        pct = (data["value"] / analytics.total_value * 100) if analytics.total_value else 0
        sector_rows.append(
            {"Sector": sector, "Value": data["value"], "%": pct, "Positions": data["count"]}
        )
    st.dataframe(
        pd.DataFrame(sector_rows).style.format(
            {"Value": f"{cur}{{:,.2f}}", "%": "{:.1f}%"}
        ),
        use_container_width=True,
        hide_index=True,
    )

with col_b:
    st.subheader("Currency Exposure")
    cur_rows = []
    for cur_code, val in analytics.currency_exposure.items():
        pct = (val / analytics.total_value * 100) if analytics.total_value else 0
        cur_rows.append({"Currency": cur_code, "Value": val, "%": pct})
    st.dataframe(
        pd.DataFrame(cur_rows).style.format(
            {"Value": f"{cur}{{:,.2f}}", "%": "{:.1f}%"}
        ),
        use_container_width=True,
        hide_index=True,
    )

# ── Concentration warnings ──
warnings = analytics.concentration_warning(threshold=25)
if warnings:
    tickers = ", ".join(
        f"{w['_ticker'].replace('_US_EQ','').replace('_EQ','')} ({w['_weight']:.1f}%)"
        for w in warnings
    )
    st.warning(f"⚠ Concentration alert: {tickers} exceed 25% weight")

# ── Auto refresh ──
time.sleep(REFRESH_SECONDS)
st.rerun()
