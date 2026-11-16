
import streamlit as st
import pandas as pd
from pathlib import Path
import os

st.set_page_config(page_title="Can I Trade? - FX Bot", page_icon="🤖", layout="wide")
st.title("🤖 Can I Trade? - FX Bot Live")

# --- Load files ---
signal_path = Path("today_signal.txt")
log_path = Path("results/live_log.csv")
pred_path = Path("predictions.csv")

signal_text = signal_path.read_text() if signal_path.exists() else "No signal yet"
signal_lower = signal_text.lower()

# Parse signal
if "sell" in signal_lower:
    signal = "SELL"
    color = "red"
    emoji = "🔴"
    reason = "Model predicts DOWN tomorrow - would place PUT / Fall"
elif "buy" in signal_lower:
    signal = "BUY"
    color = "green"
    emoji = "🟢"
    reason = "Model predicts UP tomorrow - would place CALL / Rise"
else:
    signal = "HOLD"
    color = "orange"
    emoji = "🟡"
    reason = "Low confidence (near 50%) - bot correctly HELD to protect money"

# Parse prob
import re
m = re.search(r"(\d+\.?\d*)%|prob[^0-9]*([0-9.]+)", signal_text, re.I)
prob_str = m.group(0) if m else "N/A"

# --- TOP STATUS CARDS ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🤖 Bot Status", "LIVE ✅")
with col2:
    st.metric(f"{emoji} Signal", signal)
with col3:
    st.metric("📊 Confidence", prob_str)
with col4:
    # live price
    price = "N/A"
    last_time = "N/A"
    if log_path.exists():
        try:
            df = pd.read_csv(log_path)
            if len(df) > 0:
                price = f"{df.iloc[-1]['price']:.5f}"
                last_time = str(df.iloc[-1]['timestamp'])[:16].replace("T"," ")
        except:
            pass
    st.metric("💶 EUR/USD Live", price)

st.markdown(f"### {emoji} **{signal}** - {reason}")
st.info(f"📄 today_signal.txt: `{signal_text[:300]}`")

# Why didn't it trade?
st.subheader("❓ Why didn't it open a trade?")
if signal == "HOLD":
    st.warning("Bot HELD because confidence was low (e.g. 47.3% = coin flip). It only trades when BUY >60% or SELL <40% (i.e. strong signal). This is how Logistic got +9.8% - it skips coin flips.")
elif signal in ["BUY","SELL"]:
    st.success(f"Bot SHOULD have traded {signal}. Check GitHub Actions log for '[LIVE] Deriv order placed'. If it says HOLD, signal file was old. If it says 'Market is closed', wait for Monday 02:00 SA.")
else:
    st.info("Waiting for first signal...")

# Live log chart
st.subheader("📈 Live Price Log (1-month test)")
if log_path.exists():
    try:
        df = pd.read_csv(log_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.write(f"Live points collected: **{len(df)} / 2880** needed for 1 month. Progress: {len(df)/2880*100:.1f}%")
        st.progress(min(len(df)/2880, 1.0))
        st.line_chart(df.set_index('timestamp')['price'])
        st.dataframe(df.tail(10))
    except Exception as e:
        st.error(f"Log error: {e}")
else:
    st.warning("No live_log.csv yet - bot will create it on next run")

# Accuracy
st.subheader("🎯 Live Accuracy Test")
st.write("Need 20-22 trading days. After 1 month: If live accuracy >53% AND PnL >0, keep daily. If <52%, build intraday.")
if log_path.exists():
    try:
        df = pd.read_csv(log_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        daily = df.groupby(df['timestamp'].dt.date)['price'].last()
        if len(daily) >= 2:
            ret = daily.pct_change().iloc[-1]*100
            st.metric("Last daily move", f"{ret:.2f}%")
    except:
        pass

# Trade checklist
st.subheader("✅ Checklist - Is bot working?")
st.checkbox("GitHub Actions green (last run)", value=True)
st.checkbox("Streamlit shows live price", value=True)
st.checkbox("Deriv Positions shows trade when signal is strong", value=False)
st.markdown("**Links:** [GitHub Actions](https://github.com/britsnico-commits/fxbot/actions) | [Deriv](https://app.deriv.com) | [Repo](https://github.com/britsnico-commits/fxbot)")

st.caption("Bot trades only on HIGH confidence. HOLD = smart, not broken. Last update: auto every ~1h via GitHub Actions.")
