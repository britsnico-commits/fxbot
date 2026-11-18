import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import re
import csv

Path("results").mkdir(exist_ok=True)
p = Path("results/paper_trades.csv")
now = datetime.now(timezone.utc)
today = now.strftime("%Y-%m-%d")
weekday = now.weekday()

# Weekend filter
if weekday >= 5:
    print(f"Weekend {now} - no trade")
    exit(0)

# Kill-switch
if p.exists():
    try:
        df_check = pd.read_csv(p)
        if len(df_check) > 0 and 'pnl' in df_check.columns:
            closed = df_check[df_check['status'].astype(str).str.contains('CLOSED')]
            total_pnl = float(closed['pnl'].sum()) if len(closed) > 0 else 0
            balance = 100 + total_pnl
            print(f"Balance: ${balance:.2f}")
            if balance < 70:
                print(f"KILL-SWITCH: Balance ${balance:.2f} < $70 - STOP")
                exit(0)
    except Exception as e:
        print(f"Kill-switch check failed: {e}")

# NFP Friday filter
if weekday == 4 and now.day <= 7:
    print(f"NFP Friday {today} - skipping")
    exit(0)

# Read signal
txt = Path("today_signal.txt").read_text() if Path("today_signal.txt").exists() else ""
m = re.search(r"Prob UP[^0-9]*([0-9.]+)%", txt, re.I)
prob = float(m.group(1)) if m else 50.0
ms = re.search(r"Signal:\s*(BUY|SELL|HOLD)", txt, re.I)
sig = ms.group(1).upper() if ms else "HOLD"

LOW, HIGH = 45.0, 55.0
trade_sig = "SELL" if prob < LOW else "BUY" if prob > HIGH else "HOLD"

# --- POSITION SIZING ---
# Distance from 50% = confidence
# Prob 55-60 = low confidence -> $10
# Prob 60-65 = medium -> $15
# Prob 65+ = high -> $20
# For SELL, use 100-prob
conf_prob = prob if trade_sig == "BUY" else (100 - prob if trade_sig == "SELL" else 50)
if trade_sig == "HOLD":
    stake = 0
elif conf_prob >= 65:
    stake = 20
elif conf_prob >= 60:
    stake = 15
else:
    stake = 10

print(f"Signal {trade_sig} at {prob}% -> Confidence {conf_prob:.1f}% -> Stake ${stake}")

# Dedupe - 1 per day
if p.exists():
    try:
        df = pd.read_csv(p)
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['timestamp']).dt.strftime("%Y-%m-%d")
            if today in df['date'].values:
                print(f"Already have trade for {today} - skipping")
                df = df.drop_duplicates(subset=['date'], keep='first')
                df = df.drop(columns=['date'])
                df.to_csv(p, index=False)
                exit(0)
            df = df.drop(columns=['date'])
    except Exception as e:
        print(f"Dedupe failed: {e}")

if trade_sig in ["BUY","SELL"]:
    price = 1.10
    pl = Path("results/live_log.csv")
    if pl.exists():
        try:
            d = pd.read_csv(pl)
            if len(d)>0 and 'price' in d.columns:
                price = float(d.iloc[-1]['price'])
        except:
            pass
    is_new = not p.exists()
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["timestamp","signal","prob","price","stake","type","pnl","status"])
        w.writerow([now.isoformat(), trade_sig, prob, price, stake, "1d", 0, "OPEN"])
    print(f"Logged: {trade_sig} {prob}% stake ${stake} at {price}")
else:
    print(f"HOLD {prob}% - no trade")

print("paper_trade_v2 done - position sizing active")
