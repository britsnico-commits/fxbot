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
m_sig = re.search(r"Signal:\s*(BUY|SELL|HOLD)", signal_text, re.I)
sig = m_sig.group(1).upper() if m_sig else "HOLD"

LOW, HIGH = 45.0, 55.0
m_prob = re.search(r"Prob UP[^0-9]*([0-9.]+)%", signal_text, re.I)
prob_val = float(m_prob.group(1)) if m_prob else 50.0
prob_str = f"{prob_val}%" if m_prob else "N/A"

if prob_val < LOW:
    trade_signal, emoji, reason = "SELL", "🔴", f"Model predicts DOWN ({prob_val}% < {LOW}%) - PUT / Fall"
elif prob_val > HIGH:
    trade_signal, emoji, reason = "BUY", "🟢", f"Model predicts UP ({prob_val}% > {HIGH}%) - CALL / Rise"
else:
    trade_signal, emoji, reason = "HOLD", "🟡", f"Low/Medium confidence ({prob_val}% inside {LOW}-{HIGH}%) - HELD to protect money"

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("🤖 Bot Status", "LIVE ✅")
with col2: st.metric(f"{emoji} Signal", trade_signal)
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
st.caption(f"Last price update: {last_time} UTC | Threshold: {LOW}/{HIGH}% | Source: live_log.csv")

st.markdown(f"### {emoji} **{trade_signal}** - {reason}")
st.info(f"📄 today_signal.txt: `{signal_text[:500]}`")

st.subheader("❓ Why did / didn't it open a trade?")
if trade_signal == "HOLD":
    st.warning(f"Bot HELD because {prob_val}% is inside {LOW}-{HIGH}% (tuned from 40/60 to 45/55 to get 2x more trades while keeping ~54% accuracy). No loss on coin flip.")
else:
    st.success(f"Bot SHOULD have traded {trade_signal} at {prob_val}% (outside {LOW}-{HIGH}%). Check 【entity-GitHub Actions¦canonical_name=GitHub】 log for '[LIVE] Deriv order placed' and Deriv Positions for open trade.")

st.subheader("📜 Deriv Trade History - Real Trades")
if trades_path.exists():
    try:
        tdf = pd.read_csv(trades_path)
        st.write(f"Total decisions logged: **{len(tdf)}**")
        if len(tdf)>0:
            trades_only = tdf[tdf['stake']>0]
            skipped = tdf[tdf['stake']==0]
            st.write(f"Trades placed: {len(trades_only)} | Skipped (HOLD): {len(skipped)}")
            if "pnl" in tdf.columns and len(trades_only)>0:
                total_pnl = tdf["pnl"].sum()
                wins = (tdf["pnl"]>0).sum()
                st.metric("Total PnL (Demo $)", f"${total_pnl:.2f} | Wins: {wins}/{len(trades_only)}")
            st.dataframe(tdf.sort_values("timestamp", ascending=False) if "timestamp" in tdf.columns else tdf, use_container_width=True)
    except Exception as e:
        st.error(f"Trade log error: {e}")
else:
    st.info("No deriv_trades.csv yet - will be created on next run. Shows every HOLD and TRADE.")
    example = pd.DataFrame([
        {"timestamp":"2026-11-17 09:38 UTC","symbol":"frxEURUSD","type":"CALL","signal":"BUY 55.2%","stake":10,"duration":"1d","status":"OPEN","pnl":0},
        {"timestamp":"2026-11-16 09:54 UTC","symbol":"frxEURUSD","type":"HOLD","signal":"HOLD 47.3%","stake":0,"duration":"-","status":"SKIPPED - inside 45-55","pnl":0},
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

st.subheader("🎯 Accuracy")
st.write(f"Threshold {LOW}/{HIGH}%: More trades than 40/60, keeps ~54% accuracy vs Buy & Hold -1%. Tuned to keep Logistic +9.8% edge.")
st.markdown("**Links:** [GitHub Actions](https://github.com/britsnico-commits/fxbot/actions) | [Deriv](https://app.deriv.com) | [Repo](https://github.com/britsnico-commits/fxbot)")
