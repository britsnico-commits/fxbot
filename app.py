# app.py - CANIC FXBOT - Paper Trading on LIVE Data
# Forex-only, 45/55 rule, ADX filter, shows WHY HOLD
import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="CANIC FXBOT - Paper Trading", layout="wide")
st.title("CANIC FXBOT - Paper Trading on LIVE Data")

# --- Helpers ---
def load_csv(path):
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()

def get_balance(trades):
    bal = 100.0
    profit = 0.0
    closed = 0
    wins = 0
    if len(trades) == 0:
        return bal, profit, 0.0, "0/0", bal
    # trades file has pnl column, status OPEN/CLOSED
    for _, r in trades.iterrows():
        try:
            pnl = float(r.get("pnl", 0) or 0)
            status = str(r.get("status", "")).upper()
            if status in ["CLOSED", "WIN", "LOSS", "SETTLED"]:
                closed += 1
                profit += pnl
                if pnl > 0:
                    wins += 1
        except Exception:
            pass
    bal = 100.0 + profit
    win_rate = (wins / closed * 100) if closed > 0 else 0.0
    return bal, profit, win_rate, f"{wins}/{closed}" if closed > 0 else f"0/{len(trades)}", bal

# --- Load data ---
signal_df = load_csv("results/today_signal.csv")
pred_df = load_csv("results/predictions.csv")
trades = load_csv("results/paper_trades.csv")
live = load_csv("results/live_prices.csv")
acc = load_csv("results/live_accuracy.csv")

# --- Today's Signal ---
prob = None
signal = "HOLD"
adx = 0.0
adx_note = ""
source = ""
sig_date = ""
price = 0.0
raw_signal = ""

if len(signal_df) > 0:
    r = signal_df.iloc[-1]
    try:
        prob = float(r.get("prob_up", r.get("prob", 0)))
        if prob <= 1.0 and prob != 0:
            prob = prob * 100
    except Exception:
        prob = 0.0
    signal = str(r.get("signal", "HOLD"))
    raw_signal = str(r.get("raw_signal", signal))
    try:
        adx = float(r.get("adx", 0) or 0)
    except Exception:
        adx = 0.0
    adx_note = str(r.get("adx_note", ""))
    source = str(r.get("source", ""))
    sig_date = str(r.get("date", ""))
    try:
        price = float(r.get("price", 0) or 0)
    except Exception:
        price = 0.0
elif len(pred_df) > 0:
    r = pred_df.iloc[-1]
    try:
        raw_p = float(r.get("prob_up", r.get("prob", 0)))
        prob = raw_p * 100 if raw_p <= 1.0 else raw_p
    except Exception:
        prob = 0.0
    signal = "BUY" if prob > 55 else ("SELL" if prob < 45 else "HOLD")
    raw_signal = signal
    sig_date = str(r.get("date", ""))
    try:
        price = float(r.get("price", 0) or 0)
    except Exception:
        price = 0.0
    source = "PREDICTOR_ONLY (today_signal.csv missing)"
else:
    prob = 0.0
    signal = "HOLD"
    source = "NO DATA YET - run Daily workflow"

# Top metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("Prob UP Tomorrow")
    st.header(f"{prob:.1f}%")
with col2:
    st.caption("Rule 45.0/55.0")
    st.header(signal)
with col3:
    st.caption("Model")
    st.header(signal)

# Signal detail box
st.info(
    f"Date: {sig_date} UTC\n\n"
    f"Prob UP Tomorrow: {prob:.1f}%\n\n"
    f"Signal: {signal}\n\n"
    f"Rule: 45/55 Threshold\n\n"
    f"ADX: {adx:.1f} - {adx_note if adx_note else ('CHOPPY, HOLD forced' if adx < 20 else 'TRENDING, trade allowed')}"
    + (f" (was {raw_signal})" if raw_signal and raw_signal != signal else "")
    + (f"\n\nPrice: {price:.4f}" if price else "")
    + (f"\n\nSource: {source}" if source else "")
)

st.divider()

# --- Balance / Performance ---
balance, profit, win_rate, trades_closed, _ = get_balance(trades)
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.caption("Fake Balance")
    st.header(f"${balance:.2f}")
with c2:
    st.caption("Fake Profit")
    st.header(f"${profit:.2f}")
with c3:
    st.caption("Win Rate")
    st.header(f"{win_rate:.1f}%")
with c4:
    st.caption("Trades Closed")
    st.header(trades_closed)

# --- Equity Curve ---
st.subheader("Equity Curve - Are We Winning?")
if len(trades) > 0 and "pnl" in trades.columns:
    # Build equity: start 100, add pnl of closed trades in order
    equity = [100.0]
    for _, r in trades.iterrows():
        try:
            status = str(r.get("status", "")).upper()
            if status in ["CLOSED", "WIN", "LOSS", "SETTLED"]:
                equity.append(equity[-1] + float(r.get("pnl", 0) or 0))
        except Exception:
            pass
    # If no closed trades yet, show flat 100 line (1 point is not a line, so show 2)
    if len(equity) == 1:
        equity = [100.0, 100.0]
    eq_df = pd.DataFrame({"Balance": equity})
    st.line_chart(eq_df, height=250)
else:
    st.line_chart(pd.DataFrame({"Balance": [100.0, 100.0]}), height=250)

st.caption("Start $100 fake. If line goes up over 1 month, daily model works.")

# --- Paper Trade History ---
st.subheader("Paper Trade History")
if len(trades) > 0:
    # Show newest first, clean columns
    show = trades.copy()
    # Keep expected columns if they exist
    cols = [c for c in ["timestamp", "signal", "prob", "price", "stake", "type", "pnl", "status"] if c in show.columns]
    if cols:
        show = show[cols]
    st.dataframe(show, use_container_width=True)
else:
    st.write("No trades yet. Bot will open 1 trade per day when Prob >55% or <45% and ADX >=20.")

# --- Live Price Points ---
st.subheader(f"Live Price Points: {len(live)} / 2880 (1 month)")
if len(live) > 0:
    st.progress(min(len(live) / 2880, 1.0))
    # Show last 10
    show_live = live.tail(10).copy()
    cols_live = [c for c in ["timestamp", "price"] if c in show_live.columns]
    if cols_live:
        st.dataframe(show_live[cols_live], use_container_width=True)
    else:
        st.dataframe(show_live, use_container_width=True)
else:
    st.progress(0)
    st.write("No live points yet. Daily workflow collects 1 point every 15 min.")

# --- Live Accuracy Log ---
st.subheader("Live Accuracy Log")
if len(acc) > 0:
    st.dataframe(acc, use_container_width=True)
else:
    st.write("No accuracy log yet.")

st.divider()
st.caption("CANIC FXBOT | Forex-only | EUR/USD | 1 trade/day max | $10-$20 stake | Kill-switch if balance < $70 | No trade on weekends / NFP Friday | ADX <20 = HOLD")
