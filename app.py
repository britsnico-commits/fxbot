import streamlit as st
from pathlib import Path
import re
import streamlit.components.v1 as components

st.set_page_config(page_title="CANIC FXBOT", layout="wide")
st.title("CANIC FXBOT Live Dashboard")

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
st.code(txt)

# --- CLIENT-SIDE TRADE (bypasses 520) ---
if trade_signal in ["BUY", "SELL"]:
    st.warning(f"Ready to trade {trade_signal} at {prob}% - This will trade from YOUR phone IP (SA) to bypass Deriv 520 block")
    token = st.text_input("Paste Deriv API Token here (stays in your browser, not saved on server):", type="password")
    
    ctype = "CALL" if trade_signal == "BUY" else "PUT"
    
    js_code = f"""
    <div>
      <button id="tradeBtn" style="padding:12px 24px;background:#00a651;color:white;border:none;border-radius:8px;font-size:16px;cursor:pointer;">PLACE LIVE {trade_signal} $10 FROM MY PHONE</button>
      <div id="status" style="margin-top:15px;font-family:monospace;white-space:pre-wrap;"></div>
    </div>
    <script>
      document.getElementById('tradeBtn').onclick = async () => {{
        const token = "{token}" || document.querySelector('input[type=password]')?.value || "{token}";
        // Get token from Streamlit input via URL hack - we will use prompt if empty
        let t = "{token}";
        if (!t) {{
          const input = window.parent.document.querySelectorAll('input[type=password]');
          if (input.length > 0) t = input[input.length-1].value;
        }}
        // If still empty, try the variable passed from python
        const userToken = t || "{token}" || prompt("Paste Deriv API Token:");
        if (!userToken) {{ document.getElementById('status').innerText = "No token"; return; }}
        
        const ctype = "{ctype}";
        const log = (m) => {{ document.getElementById('status').innerText += m + "\\n"; }};
        log("Connecting from your phone IP to Deriv...");
        try {{
          const ws = new WebSocket("wss://ws.derivws.com/websockets/v3?app_id=1089");
          ws.onopen = () => {{
            log("WS connected - authorizing...");
            ws.send(JSON.stringify({{authorize: userToken}}));
          }};
          ws.onmessage = (e) => {{
            const data = JSON.parse(e.data);
            log("Recv: " + JSON.stringify(data).substring(0,300));
            if (data.error) {{ log("Error: " + data.error.message); ws.close(); return; }}
            if (data.authorize) {{
              log("Authorized OK - sending proposal {ctype}...");
              ws.send(JSON.stringify({{proposal:1, amount:10, basis:"stake", contract_type:ctype, currency:"USD", duration:1, duration_unit:"d", symbol:"frxEURUSD"}}));
            }} else if (data.proposal) {{
              log("Proposal OK id=" + data.proposal.id + " - buying...");
              ws.send(JSON.stringify({{buy: data.proposal.id, price:10}}));
            }} else if (data.buy) {{
              log("✅ LIVE ORDER PLACED: " + JSON.stringify(data.buy));
              ws.close();
            }}
          }};
          ws.onerror = (e) => {{ log("WS Error: " + e); }};
        }} catch(err) {{ log("Error: " + err); }}
      }};
    </script>
    """
    # Simple version without token input dependency - use direct JS prompt
    components.html(f"""
    <div>
      <button onclick="doTrade()" style="padding:14px 24px;background:#00a651;color:white;border:none;border-radius:8px;font-size:16px;cursor:pointer;width:100%;">PLACE LIVE {trade_signal} $10 - TAP HERE (From SA IP)</button>
      <div id="s" style="margin-top:12px;font-family:monospace;background:#f5f5f5;padding:10px;border-radius:6px;white-space:pre-wrap;max-height:300px;overflow:auto;"></div>
    </div>
    <script>
    function doTrade(){{
      const token = prompt("Paste your Deriv API Token:");
      if(!token) return;
      const ctype = "{ctype}";
      const s = document.getElementById('s');
      const log = (m) => {{ s.innerText += m+"\\n"; console.log(m); }};
      log("Connecting from YOUR phone to ws.derivws.com...");
      const ws = new WebSocket("wss://ws.derivws.com/websockets/v3?app_id=1089");
      ws.onopen = () => {{ log("Connected - Authorizing..."); ws.send(JSON.stringify({{authorize: token}})); }};
      ws.onmessage = (msg) => {{
        const d = JSON.parse(msg.data);
        log("<< " + JSON.stringify(d).slice(0,400));
        if(d.error){{ log("❌ "+d.error.message); ws.close(); return; }}
        if(d.authorize){{ log("Auth OK - Proposal "+ctype); ws.send(JSON.stringify({{proposal:1, amount:10, basis:"stake", contract_type:ctype, currency:"USD", duration:1, duration_unit:"d", symbol:"frxEURUSD"}})); }}
        else if(d.proposal){{ log("Proposal OK - Buying..."); ws.send(JSON.stringify({{buy:d.proposal.id, price:10}})); }}
        else if(d.buy){{ log("✅✅ LIVE TRADE PLACED: "+JSON.stringify(d.buy)); }}
      }};
      ws.onerror = (e)=>{{ log("WS Error - Deriv may block, try again"); }};
    }}
    </script>
    """, height=400)
else:
    st.info(f"HOLD - {prob}% inside {LOW}-{HIGH}%")

p = Path("results/deriv_trades.csv")
if p.exists():
    st.subheader("Real Trade History")
    st.dataframe(pd.read_csv(p).tail(20))
