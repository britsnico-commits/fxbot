import streamlit as st
import pandas as pd
from pathlib import Path
import re

st.set_page_config(page_title="CANIC FXBOT", layout="wide")
st.title("CANIC FXBOT - Paper Trading on LIVE Data")

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

# --- EQUITY CURVE ---
p_trades = Path("results/paper_trades.csv")
if p_trades.exists():
    try:
        df = pd.read_csv(p_trades)
        if len(df) > 0 and 'pnl' in df.columns:
            # Only closed trades count for equity
            closed = df[df['status'].astype(str).str.contains('CLOSED')].copy()
            # For display, also include OPEN as 0 for now
            total_pnl = float(df[df['status'].astype(str).str.contains('CLOSED')]['pnl'].sum()) if len(closed)>0 else 0
            win = float((closed['pnl'] > 0).mean()*100) if len(closed)>0 else 0
            start_balance = 100
            equity = [start_balance]
            for pnl in closed['pnl'].tolist():
                equity.append(equity[-1] + pnl)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fake Balance", f"${equity[-1]:.2f}")
            c2.metric("Fake Profit", f"${total_pnl:.2f}")
            c3.metric("Win Rate", f"{win:.1f}%")
            c4.metric("Trades Closed", f"{len(closed)}/{len(df)}")

            st.subheader("Equity Curve - Are We Winning?")
            # Build equity df for chart
            eq_df = pd.DataFrame({"Balance": equity})
            st.line_chart(eq_df, height=250)
            st.caption("Start $100 fake. If line goes up over 1 month, daily model works.")

            st.subheader("Paper Trade History")
            st.dataframe(df.tail(30))
        else:
            st.info("No trades yet")
    except Exception as e:
        st.write(f"Equity error: {e}")
else:
    st.info("No paper trades yet")

# --- Live Points ---
p_live = Path("results/live_log.csv")
if p_live.exists():
    try:
        df_live = pd.read_csv(p_live)
        st.subheader(f"Live Price Points: {len(df_live)} / 2880 (1 month)")
        st.progress(min(len(df_live)/2880, 1.0))
        st.dataframe(df_live.tail(10))
    except Exception as e:
        st.write(f"live_log error: {e}")

# --- Accuracy ---
p_acc = Path("results/live_accuracy.csv")
if p_acc.exists():
    st.subheader("Live Accuracy Log")
    st.dataframe(pd.read_csv(p_acc).tail(20))
