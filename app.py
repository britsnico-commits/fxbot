import streamlit as st
from pathlib import Path
import pandas as pd
import re
import streamlit.components.v1 as components

st.set_page_config(page_title="CANIC FXBOT", layout="wide")
st.title("CANIC FXBOT Live Dashboard")

# --- Signal ---
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

c1, c2, c3 = st.columns(3)
c1.metric("Prob UP tomorrow", f"{prob}%")
c2.metric(f"Rule {LOW}/{HIGH}", trade_signal)
c3.metric("Model Signal", signal)
st.code(txt, language="text")

# --- CLIENT TRADE FROM YOUR SA PHONE ---
if trade_signal in ["BUY", "SELL"]:
    ctype = "CALL" if trade_signal == "BUY" else "PUT"
    st.success(f"Ready to trade {trade_signal} at {prob}%")
    components.html(f"""
    <div>
      <button onclick="doTrade()" style="padding:14px 24px;background:#00a651;color:white;border:none;border-radius:8px;font-size:16px;cursor:pointer;width:100%;font-weight:bold;">PLACE LIVE {trade_signal} $10 - TAP HERE (SA IP Bypass 520)</button>
      <div id="s" style="margin-top:12px;font-family:monospace;background:#f5f5f5;padding:10px;border-radius:6px;white-space:pre-wrap;max-height:300px;overflow:auto;"></div>
    </div>
    <script>
    function doTrade(){{
      const token = prompt("Paste Deriv API Token (from Deriv -> API Token):");
      if(!token) return;
      const ctype = "{ctype}";
      const s = document.getElementById('s');
      const log = (m) => {{ s.innerText += m+"\\n"; }};
      log("Connecting from YOUR phone IP to Deriv...");
      const ws = new WebSocket("wss://ws.derivws.com/websockets/v3?app_id=1089");
      ws.onopen = () => {{ log("Connected - Authorizing..."); ws.send(JSON.stringify({{authorize: token}})); }};
      ws.onmessage = (msg) => {{
        const d = JSON.parse(msg.data);
        log("<< "+JSON.stringify(d).slice(0,500));
        if(d.error){{ log("❌ "+d.error.message); ws.close(); return; }}
        if(d.authorize){{ log("Auth OK - Proposal "+ctype); ws.send(JSON.stringify({{proposal:1, amount:10, basis:"stake", contract_type:ctype, currency:"USD", duration:1, duration_unit:"d", symbol:"frxEURUSD"}})); }}
        else if(d.proposal){{ log("Proposal OK id="+d.proposal.id+" - Buying..."); ws.send(JSON.stringify({{buy:d.proposal.id, price:10}})); }}
        else if(d.buy){{ log("✅✅ LIVE TRADE PLACED: "+JSON.stringify(d.buy)); log("Check Deriv App -> Positions"); }}
      }};
      ws.onerror = (e)=>{{ log("WS Error"); }};
    }}
    </script>
    """, height=450)
else:
    st.info(f"HOLD - {prob}% inside {LOW}-{HIGH}% - no trade needed")

st.divider()

# --- DATA WE WANT TO RECORD ---
# 1. Live log
p_live = Path("results/live_log.csv")
if p_live.exists():
    try:
        df = pd.read_csv(p_live)
        st.subheader(f"Live Price Log: {len(df)} points (Goal 2880 = 1 month)")
        st.dataframe(df.tail(20))
        st.progress(min(len(df)/2880, 1.0))
    except Exception as e:
        st.write(f"live_log error: {e}")
else:
    st.write("No live_log.csv yet")

# 2. Live accuracy
p_acc = Path("results/live_accuracy.csv")
if p_acc.exists():
    st.subheader("Live Accuracy")
    st.dataframe(pd.read_csv(p_acc).tail(20))

# 3. Predictions
p_pred = Path("predictions.csv")
if p_pred.exists():
    st.subheader("Predictions.csv")
    st.dataframe(pd.read_csv(p_pred).tail(20))

# 4. Deriv trades
p_deriv = Path("results/deriv_trades.csv")
if p_deriv.exists():
    st.subheader("Deriv Trade History")
    try:
        st.dataframe(pd.read_csv(p_deriv).tail(30))
    except:
        st.write(Path(p_deriv).read_text()[-1000:])
