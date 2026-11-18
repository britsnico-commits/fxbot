import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import re
import csv

Path("results").mkdir(exist_ok=True)
p = Path("results/paper_trades.csv")
now = datetime.now(timezone.utc)
today = now.strftime("%Y-%m-%d")
weekday = now.weekday()  # 0=Mon, 5=Sat, 6=Sun

# --- 1. WEEKEND FILTER ---
if weekday >= 5:
    print(f"Weekend {now} - market closed, no trade")
    exit(0)

# --- 2. KILL-SWITCH: Stop if Fake Balance < $70 ---
# Start $100, stop at -30%
if p.exists():
    try:
        df_check = pd.read_csv(p)
        if len(df_check) > 0 and 'pnl' in df_check.columns:
            closed = df_check[df_check['status'].astype(str).str.contains('CLOSED')]
            total_pnl = float(closed['pnl'].sum()) if len(closed) > 0 else 0
            balance = 100 + total_pnl
            print(f"Current Fake Balance: ${balance:.2f}")
            if balance < 70:
                print(f"KILL-SWITCH TRIGGERED: Balance ${balance:.2f} < $70 - STOPPING ALL TRADES")
                exit(0)
    except Exception as e:
        print(f"Kill-switch check failed: {e}")

# --- 3. NFP FILTER: First Friday of month = no trade (coin flip day) ---
# NFP is first Friday, 14:30 SA time. Skip whole day to avoid fake loss.
if weekday == 4:  # Friday
    # Check if first Friday: day <=7
    if now.day <= 7:
        print(f"NFP Friday {today} - skipping trade (high volatility)")
        exit(0)

# --- Normal 1-trade-per-day logic ---
txt = Path("today_signal.txt").read_text() if Path("today_signal.txt").exists() else ""
m = re.search(r"Prob UP[^0-9]*([0-9.]+)%", txt, re.I)
prob = float(m.group(1)) if m else 50.0
ms = re.search(r"Signal:\s*(BUY|SELL|HOLD)", txt, re.I)
sig = ms.group(1).upper() if ms else "HOLD"

LOW, HIGH = 45.0, 55.0
trade_sig = "SELL" if prob < LOW else "BUY" if prob > HIGH else "HOLD"

# Dedupe - 1 trade per day max
if p.exists():
    try:
        df = pd.read_csv(p)
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['timestamp']).dt.strftime("%Y-%m-%d")
            if today in df['date'].values:
                print(f"Already have trade for {today} - skipping duplicate")
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
        w.writerow([now.isoformat(), trade_sig, prob, price, 10, "1d", 0, "OPEN"])
    print(f"Paper trade logged: {trade_sig} {prob}% at {price} for {today}")
else:
    print(f"HOLD {prob}% - no trade")

print("paper_trade_v2 done - kill-switch + weekend + NFP filters active")
