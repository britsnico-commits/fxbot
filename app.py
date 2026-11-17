import streamlit as st
import pandas as pd
from pathlib import Path
import re
import json
import os
import websocket

st.set_page_config(page_title="CANIC FXBOT", layout="wide")
st.title("CANIC FXBOT Live Dashboard")

# --- Deriv Live Trade Function ---
def place_deriv_trade(signal, prob):
    try:
        token = st.secrets.get("DERIV_API_TOKEN") if "DERIV_API_TOKEN" in st.secrets else os.getenv("DERIV_API_TOKEN")
        if not token:
            return "❌ No DERIV_API_TOKEN in Streamlit Secrets"
        ctype = "CALL" if signal == "BUY" else "PUT"
        ws = websocket.create_connection(
            "wss://ws.derivws.com/websockets/v3?app_id=1089",
            timeout=20,
            header=["Origin: https://app.deriv.com", "User-Agent: Mozilla/5.0"]
        )
        ws.send(json.dumps({"authorize": token}))
        auth = json.loads(ws.recv())
        if "error" in auth:
            ws.close()
            return f"Auth failed: {auth['error']['message']}"
        ws.send(json.dumps({
            "proposal": 1, "amount": 10, "basis": "stake",
            "contract_type": ctype, "currency": "USD",
            "duration": 1, "duration_unit": "d", "symbol": "frxEURUSD"
        }))
        prop = json.loads(ws.recv())
        if "error" in prop:
            ws.close()
            return f"Proposal failed: {prop['error']['message']}"
        pid = prop["proposal"]["id"]
        ws.send(json.dumps({"buy": pid, "price": 10}))
        buy = json.loads(ws.recv())
        ws.close()
        if "error" in buy:
            return f"Buy failed: {buy['error']['message']}"
        return f"✅ [LIVE] Deriv order placed: {ctype} frxEURUSD 1d $10 at {prob}%"
    except Exception as e:
        return f"Trade error: {e}"

# --- Read Signal ---
signal_path = Path("today_signal.txt")
prob = 50.0
signal = "HOLD"
txt = "No signal yet"
if signal_path.exists():
    txt = signal_path.read_text()
    m = re.search(r"Prob UP[^0-9]*([0-9.]+)%", txt, re.I)
    if m:
        prob = float(m.group(1))
    ms = re.search(r"Signal:\s*(BUY|SELL|HOLD)", txt, re.I)
    if ms:
        signal = ms.group(1).upper()

LOW, HIGH = 45.0, 55.0
trade_signal = "HOLD"
if prob < LOW: trade_signal = "SELL"
elif prob > HIGH: trade_signal = "BUY"

col1, col2, col3 = st.columns(3)
col1.metric("Prob UP tomorrow", f"{prob}%")
col2.metric(f"Rule {LOW}/{HIGH} Trade Signal", trade_signal)
col3.metric("Model Signal", signal)

st.code(txt, language="text")

# --- Trade Section ---
if trade_signal in ["BUY", "SELL"]:
    st.warning(f"Ready to trade {trade_signal} at {prob}%")
    if st.button(f"Place LIVE Deriv {trade_signal} $10"):
        with st.spinner("Connecting to Deriv..."):
            result = place_deriv_trade(trade_signal, prob)
        if "LIVE" in result:
            st.success(result)
            st.balloons()
        else:
            st.error(result)
else:
    st.info(f"HOLD - {prob}% inside {LOW}-{HIGH}% - no trade needed")

# --- Show Deriv Trades Log ---
p = Path("results/deriv_trades.csv")
if p.exists():
    st.subheader("Real Trade History")
    st.dataframe(pd.read_csv(p).tail(20))
