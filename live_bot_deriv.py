import os
from datetime import datetime, timezone
from pathlib import Path
import re

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
else:
    log("today_signal.txt not found, fallback HOLD")

LOW = 45.0
HIGH = 55.0

if prob < LOW:
    trade_signal = "SELL"
elif prob > HIGH:
    trade_signal = "BUY"
else:
    trade_signal = "HOLD"

log(f"Original Signal: {signal}, Prob: {prob}%, Tuned Rule {LOW}/{HIGH} => Trade Signal: {trade_signal}")

if trade_signal == "HOLD":
    log(f"HOLD because {prob}% is inside {LOW}-{HIGH}%")
    try:
        import csv
        Path("results").mkdir(exist_ok=True)
        p = Path("results/deriv_trades.csv")
        is_new = not p.exists()
        with open(p, "a", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["timestamp","symbol","type","signal","stake","duration","status","pnl"])
            w.writerow([now.isoformat(), "frxEURUSD", "HOLD", f"{signal} {prob}%", 0, "-", f"SKIPPED - {prob}% inside {LOW}-{HIGH}", 0])
    except Exception as e:
        log(f"Log skipped failed: {e}")
    exit(0)

try:
    from deriv_api import DerivAPI
    import asyncio
    log("deriv_api imported ok")
except Exception as e:
    log(f"deriv_api import failed: {e} - DRY RUN would place {trade_signal}")
    log(f"[DRY RUN] Would place {trade_signal} frxEURUSD 1d $10 at {prob}%")
    exit(0)

async def place_order():
    try:
        api = DerivAPI(app_id=1089)
        await api.connect()
        await api.authorize(TOKEN)
        log("Deriv authorized OK")
        bal = await api.balance()
        log(f"Balance: {bal}")
        contract_type = "PUT" if trade_signal == "SELL" else "CALL"
        log(f"Placing order: {contract_type} frxEURUSD 1d $10 at {prob}%")
        proposal = await api.proposal({
            "proposal": 1,
            "amount": 10,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "duration": 1,
            "duration_unit": "d",
            "symbol": "frxEURUSD"
        })
        log(f"Proposal: {proposal}")
        if "proposal" in proposal:
            buy = await api.buy({"buy": proposal["proposal"]["id"], "price": 10})
            log(f"[LIVE] Deriv order placed: {contract_type} frxEURUSD 1d $10 at {prob}%")
            log(f"Buy response: {buy}")
            try:
                import csv
                Path("results").mkdir(exist_ok=True)
                p = Path("results/deriv_trades.csv")
                is_new = not p.exists()
                with open(p, "a", newline="") as f:
                    w = csv.writer(f)
                    if is_new:
                        w.writerow(["timestamp","symbol","type","signal","stake","duration","status","pnl"])
                    w.writerow([now.isoformat(), "frxEURUSD", contract_type, f"{trade_signal} {prob}%", 10, "1d", "OPEN", 0])
                log("Logged to deriv_trades.csv")
            except Exception as e:
                log(f"CSV log failed: {e}")
        else:
            log(f"Proposal failed: {proposal}")
        await api.disconnect()
    except Exception as e:
        log(f"Order failed: {e}")
        import traceback
        traceback.print_exc()

import asyncio
asyncio.run(place_order())
log("live_bot_deriv.py done - 45/55 threshold")
