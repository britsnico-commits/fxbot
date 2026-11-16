
import streamlit as st
import pandas as pd
from pathlib import Path
import re

st.set_page_config(page_title="Can I Trade? - FX Bot", page_icon="🤖", layout="wide")
st.title("🤖 Can I Trade? - FX Bot Live")

signal_path = Path("today_signal.txt")
log_path = Path("results/live_log.csv")
trades_path = Path("results/deriv_trades.csv")

signal_text = signal_path.read_text() if signal_path.exists() else "No signal yet"
sl = signal_text.lower()

if "sell" in sl:
    signal, emoji, reason = "SELL", "🔴", "Model predicts DOWN - would place PUT / Fall"
elif "buy" in sl:
    signal, emoji, reason = "BUY", "🟢", "Model predicts UP - would place CALL / Rise"
else:
    signal, emoji, reason = "HOLD", "🟡", "Low confidence (near 50%) - bot correctly HELD to protect money"

m = re.search(r"(\d+\.?\d*)%|prob[^0-9]*([0-9.]+)", signal_text, re.I)
prob_str = m.group(0) if m else "N/A"

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("🤖 Bot Status", "LIVE ✅")
with col2: st.metric(f"{emoji} Signal", signal)
with col3: st.metric("📊 Confidence", prob_str)
with col4:
    price, last_time = "N/A", "N/A"
    if log_path.exists():
        try:
            df = pd.read_csv(log_path)
            if len(df)>0:
                price = f"{df.iloc[-1]['price']:.5f}"
                last_time = str(df.iloc[-1]['timestamp'])[:16].replace("T"," ")
        except: pass
    st.metric("💶 EUR/USD Live", price)
st.caption(f"Last price update: {last_time} UTC | Source: live_log.csv")

st.markdown(f"### {emoji} **{signal}** - {reason}")
st.info(f"📄 today_signal.txt: `{signal_text[:300]}`")

st.subheader("❓ Why didn't it open a trade?")
if signal == "HOLD":
    st.warning("Bot HELD because confidence was low (e.g. 47.3% = coin flip). It only trades when BUY >60% or SELL <40%. This is how Logistic got +9.8% - it skips coin flips.")
elif signal in ["BUY","SELL"]:
    st.success(f"Bot SHOULD have traded {signal}. Check GitHub Actions log for '[LIVE] Deriv order placed'. If it says HOLD, signal was old. If 'Market is closed', wait for Monday 02:00 SA.")

# --- DERIV TRADE HISTORY ---
st.subheader("📜 Deriv Trade History - Real Trades")
if trades_path.exists():
    try:
        tdf = pd.read_csv(trades_path)
        st.write(f"Total trades placed: **{len(tdf)}**")
        if len(tdf)>0:
            # PnL summary if columns exist
            if "pnl" in tdf.columns:
                total_pnl = tdf["pnl"].sum()
                wins = (tdf["pnl"]>0).sum()
                st.metric("Total PnL (Demo $)", f"${total_pnl:.2f} | Wins: {wins}/{len(tdf)}")
            st.dataframe(tdf.sort_values("timestamp", ascending=False) if "timestamp" in tdf.columns else tdf, use_container_width=True)
            # chart PnL over time
            if "pnl" in tdf.columns and len(tdf)>1:
                st.line_chart(tdf["pnl"].cumsum())
        else:
            st.info("Trade log exists but empty - no trades yet. Bot is waiting for HIGH confidence.")
    except Exception as e:
        st.error(f"Trade log error: {e}")
else:
    st.info("No trades yet - `results/deriv_trades.csv` not created. Bot has only HELD so far (low confidence). When it trades, it will appear here automatically.")
    # Show example of what table will look like
    st.write("**What it will look like when it trades:**")
    example = pd.DataFrame([
        {"timestamp":"2026-11-17 07:10 UTC","symbol":"frxEURUSD","type":"PUT","signal":"SELL","stake":10,"duration":"1d","status":"OPEN","pnl":0},
        {"timestamp":"2026-11-16 07:10 UTC","symbol":"frxEURUSD","type":"HOLD","signal":"BUY 47.3%","stake":0,"duration":"-","status":"SKIPPED - Low confidence","pnl":0},
    ])
    st.dataframe(example, use_container_width=True)

st.subheader("📈 Live Price Log (1-month test)")
if log_path.exists():
    try:
        df = pd.read_csv(log_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.write(f"Live points: **{len(df)} / 2880** ({len(df)/2880*100:.1f}%)")
        st.progress(min(len(df)/2880,1.0))
        st.line_chart(df.set_index('timestamp')['price'])
        st.dataframe(df.tail(10))
    except Exception as e: st.error(e)
else:
    st.warning("No live_log.csv yet")

st.subheader("🎯 Live Accuracy")
st.write("Need 20-22 days. >53% + PnL >0 = keep daily. <52% = build intraday.")
st.markdown("**Links:** [GitHub Actions](https://github.com/britsnico-commits/fxbot/actions) | [Deriv Positions](https://app.deriv.com) | [Repo](https://github.com/britsnico-commits/fxbot)")
st.caption("HOLD = smart, not broken. Bot logs every decision to deriv_trades.csv")
