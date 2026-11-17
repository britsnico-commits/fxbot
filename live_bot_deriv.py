import os
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import csv

def log(msg):
    print(msg, flush=True)

TOKEN = os.getenv("DERIV_API_TOKEN")
if not TOKEN:
    log("ERROR: DERIV_API_TOKEN not found!")
    exit(0)

now = datetime.now(timezone.utc)
weekday = now.weekday()
log(f"Now UTC: {now} weekday={weekday}")

if weekday >= 5:
    log("Market is closed - weekend, skipping")
    exit(0)

signal_path = Path("today_signal.txt")
prob = 50.0
signal = "HOLD"
txt = ""
if signal_path.exists():
    txt = signal_path.read_text()
    log(f"today_signal.txt: {txt[:400]}")
    m = re.search(r"Prob UP[^0-9]*([0-9.]+)%", txt, re.I)
    if m:
        prob = float(m.group(1))
        log(f"Parsed prob UP: {prob}%")
    m_sig = re.search(r"Signal:\s*(BUY|SELL|HOLD)", txt, re.I)
    if m_sig:
        signal = m_sig.group(1).upper()

LOW, HIGH = 45.0, 55.0
if prob < LOW:
    trade_signal = "SELL"
elif prob > HIGH:
    trade_signal = "BUY"
else:
    trade_signal = "HOLD"

log(f"Tuned Rule {LOW}/{HIGH} => Trade Signal: {trade_signal} at {prob}%")

if trade_signal == "HOLD":
    log(f"HOLD because {prob}% inside {LOW}-{HIGH}%")
    try:
        Path("results").mkdir(exist_ok=True)
        p = Path("results/deriv_trades.csv")
        is_new = not p.exists()
        with open(p, "a", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["timestamp","symbol","type","signal","stake","duration","status","pnl"])
            w.writerow([now.isoformat(), "frxEURUSD", "HOLD", f"{signal} {prob}%", 0, "-", f"SKIPPED - {prob}% inside {LOW}-{HIGH}", 0])
        log("Logged HOLD")
    except Exception as e:
        log(f"CSV log failed: {e}")
    exit(0)

try:
    import websocket
    log("websocket-client imported ok")
except Exception as e:
    log(f"websocket-client missing: {e}")
    exit(0)

contract_type = "PUT" if trade_signal == "SELL" else "CALL"
log(f"Placing order: {contract_type} frxEURUSD 1d $10 at {prob}%")

endpoints = [
    "wss://ws.derivws.com/websockets/v3?app_id=1089",
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
    "wss://ws.deriv.com/websockets/v3?app_id=1089"
]

success = False
for ws_url in endpoints:
    try:
        log(f"Trying WS: {ws_url}")
        ws = websocket.create_connection(ws_url, timeout=25, header=["Origin: https://app.deriv.com", "User-Agent: Mozilla/5.0"])
        log(f"WS connected to {ws_url}")

        ws.send(json.dumps({"authorize": TOKEN}))
        resp = json.loads(ws.recv())
        log(f"Authorize resp: {str(resp)[:300]}")
        if "error" in resp:
            log(f"Auth failed: {resp['error']}")
            ws.close()
            continue
        log("Deriv authorized OK")

        proposal_req = {
            "proposal": 1,
            "amount": 10,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "duration": 1,
            "duration_unit": "d",
            "symbol": "frxEURUSD"
        }
        ws.send(json.dumps(proposal_req))
        proposal_resp = json.loads(ws.recv())
        log(f"Proposal resp: {str(proposal_resp)[:500]}")

        if "error" in proposal_resp:
            log(f"Proposal error: {proposal_resp['error']}")
            ws.close()
            continue

        if "proposal" not in proposal_resp:
            log(f"No proposal: {proposal_resp}")
            ws.close()
            continue

        proposal_id = proposal_resp["proposal"]["id"]
        log(f"Proposal ID: {proposal_id}")

        buy_req = {"buy": proposal_id, "price": 10}
        ws.send(json.dumps(buy_req))
        buy_resp = json.loads(ws.recv())
        log(f"Buy resp: {str(buy_resp)[:500]}")

        if "error" in buy_resp:
            log(f"Buy error: {buy_resp['error']}")
            ws.close()
            continue
        else:
            log(f"[LIVE] Deriv order placed: {contract_type} frxEURUSD 1d $10 at {prob}% - via {ws_url}")
            try:
                Path("results").mkdir(exist_ok=True)
                p = Path("results/deriv_trades.csv")
                is_new = not p.exists()
                with open(p, "a", newline="") as f:
                    w = csv.writer(f)
                    if is_new:
                        w.writerow(["timestamp","symbol","type","signal","stake","duration","status","pnl"])
                    w.writerow([now.isoformat(), "frxEURUSD", contract_type, f"{trade_signal} {prob}%", 10, "1d", "OPEN", 0])
                log("Logged LIVE trade")
            except Exception as e:
                log(f"CSV log failed: {e}")
            ws.close()
            success = True
            break

    except Exception as e:
        log(f"Endpoint {ws_url} failed: {e}")
        try:
            ws.close()
        except:
            pass
        time.sleep(2)
        continue

if not success:
    log("All endpoints failed - will retry next run. Saving as DRY RUN for now.")
    try:
        Path("results").mkdir(exist_ok=True)
        p = Path("results/deriv_trades.csv")
        is_new = not p.exists()
        with open(p, "a", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["timestamp","symbol","type","signal","stake","duration","status","pnl"])
            w.writerow([now.isoformat(), "frxEURUSD", contract_type, f"{trade_signal} {prob}%", 10, "1d", "DRY_RUN_520", 0])
        log("Logged DRY RUN due to 520")
    except Exception as e:
        log(f"CSV log failed: {e}")

log("live_bot_deriv.py done - 45/55 threshold - multi-endpoint")
