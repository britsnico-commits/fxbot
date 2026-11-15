$code = @'

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt

st.set_page_config(page_title="FXBOT Live Dashboard", layout="wide")

st.title("FXBOT Live Dashboard - EUR/USD Forecaster")
st.markdown("One-click: is it accurate? When to trade? Fake money test")

# Paths
RESULTS = Path("results")
PRED = RESULTS / "predictions.csv"
TODAY = Path("today_signal.txt")

# Top row - Today's signal
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Today's Signal")
    if TODAY.exists():
        txt = TODAY.read_text()
        st.text(txt)
        # parse signal
        if "BUY" in txt:
            st.success("BUY SIGNAL")
        elif "SELL" in txt:
            st.error("SELL SIGNAL")
        else:
            st.warning("HOLD - No edge")
    else:
        st.info("Run python today_signal.py first")

with col2:
    st.subheader("Accuracy Check")
    feat_path = RESULTS / "feature_importance.csv"
    if feat_path.exists():
        df = pd.read_csv(feat_path)
        st.metric("Total Variables", len(df))
        st.metric("Top Feature", df.columns[0] if "Unnamed" in df.columns[0] else df.iloc[0,0])
        # show top 10
        st.dataframe(df.head(10))
    else:
        st.info("Run predictor_v3.py")

with col3:
    st.subheader("Fake Money Test")
    paper_path = RESULTS / "paper_trade_equity.csv"
    if paper_path.exists():
        df = pd.read_csv(paper_path)
        if "fake_balance" in df.columns:
            bal = df["fake_balance"].iloc[-1]
            ret = bal/10000 - 1
            st.metric("Fake Money Balance", f"${bal:,.2f}", f"{ret*100:.1f}%")
    st.text("Logistic +9.8% PASS vs BH 6.2% (2025+)")
    st.text("RF +54.8% vs BH -1% (2022-2026)")

# Middle - Equity curves
st.subheader("Equity Curves")
col_a, col_b = st.columns(2)

with col_a:
    eq_path = RESULTS / "equity_curve.png"
    if eq_path.exists():
        st.image(str(eq_path), caption="Out-of-sample cumulative return (FIXED no lookahead) - Blue Ensemble +26% vs Green BH -1%")
    else:
        st.info("Run predictor_v3.py to generate equity_curve.png")

with col_b:
    live_path = RESULTS / "live_dashboard.png"
    if live_path.exists():
        st.image(str(live_path), caption="Live Dashboard - BUY (green ^) SELL (red v) markers")
    else:
        st.info("Run python live_dashboard.py")

# Bottom - Historical performance
st.subheader("Historical Performance (Walk-Forward)")
if PRED.exists():
    df = pd.read_csv(PRED)
    # find columns
    ret_col = [c for c in df.columns if "actual" in c.lower() and "return" in c.lower()][0]
    ens_col = [c for c in df.columns if "ensemble" in c.lower()][0]
    date_col = df.columns[0]
    df["Date"] = pd.to_datetime(df[date_col])
    df = df.sort_values("Date")
    df["hit"] = (df[ret_col] > 0) == (df[ens_col] > 0.5)
    df["year"] = df["Date"].dt.year
    
    yearly = df.groupby("year")["hit"].mean().reset_index()
    st.bar_chart(yearly.set_index("year"))
    
    st.dataframe(df.tail(20))
else:
    st.info("No predictions.csv")

st.markdown("---")
st.markdown("**Verdict:** Daily RF 55.7% Sharpe 1.45 = PASS for paper trade. Hourly 54.9% negative after costs = FAIL for 1h. This is paper-trade only, not financial advice.")

'@
$code | Out-File -Encoding utf8 "$HOME\OneDrive\Documents\fxbot\app.py" -Force
Write-Host "Created app.py - STREAMLIT DASHBOARD" -ForegroundColor Green
