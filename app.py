import streamlit as st
import pandas as pd
from pathlib import Path
import re

st.set_page_config(page_title="CANIC FXBOT", layout="wide")
st.title("CANIC FXBOT - Paper Trading on LIVE Data (No Deriv 520)")

txt_path = Path("today_signal.txt")
txt = txt_path.read_text() if txt_path.exists() else "No signal yet"
m = re.search(r"Prob UP[^0-9]*([0-9.]+)%", txt, re.I)
prob = float(m.group(1)) if m else 50.0
ms = re.search(r"Signal:\s*(BUY|SELL|HOLD)", txt, re.I)
signal = ms.group(1).upper() if ms else "HOLD"

LOW, HIGH = 45.0, 55.0
trade_sig = "SELL" if prob < LOW else "BUY" if prob > HIGH else "HOLD"

c1, c2, c3 = st.columns(3)
c1.metric("Prob UP Tomorrow", f"{prob}%")
c2.metric(f"Rule {LOW}/{HIGH}", trade_sig)
c3.metric("Model", signal)
st.code(txt)

st.divider()

# Live points collection
p_live = Path("results/live_log.csv")
if p_live.exists():
    try:
        df_live = pd.read_csv(p_live)
        st.subheader(f"Live Price Points: {len(df_live)} / 2880 (1 month goal)")
        st.progress(min(len(df_live)/2880, 1.0))
        st.dataframe(df_live.tail(15))
    except Exception as e:
        st.write(f"live_log read error: {e}")
else:
    st.info("Collecting live_log.csv...")

# Paper trades - THIS IS YOUR FAKE LIVE TRADING
found = False
for name in ["results/paper_trades.csv", "results/paper_trade_results.csv", "results/paper_trade_v2.csv"]:
    p = Path(name)
    if p.exists():
        try:
            df = pd.read_csv(p)
            pnl_col = None
            for col in df.columns:
                if "pnl" in col.lower() or "profit" in col.lower():
                    pnl_col = col
                    break
            total = df[pnl_col].sum() if pnl_col else 0
            win = (df[pnl_col] > 0).mean()*100 if pnl_col and len(df)>0 else 0
            st.subheader(f"Fake Live Profit: ${total:.2f} | Win {win:.1f}% | Trades {len(df)}")
            st.dataframe(df.tail(30))
            found = True
            break
        except Exception as e:
            st.write(f"{name} error: {e}")
if not found:
    st.info("No paper trades yet - will appear after next run when signal BUY/SELL")

# Accuracy
p_acc = Path("results/live_accuracy.csv")
if p_acc.exists():
    st.subheader("Live Accuracy Check")
    st.dataframe(pd.read_csv(p_acc).tail(20))

# Predictions
p_pred = Path("predictions.csv")
if p_pred.exists():
    st.subheader("Predictions")
    st.dataframe(pd.read_csv(p_pred).tail(20))
