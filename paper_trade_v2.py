import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import re
import csv

Path("results").mkdir(exist_ok=True)
p = Path("results/paper_trades.csv")

txt = Path("today_signal.txt").read_text() if Path("today_signal.txt").exists() else ""
m = re.search(r"Prob UP[^0-9]*([0-9.]+)%", txt, re.I)
prob = float(m.group(1)) if m else 50.0
ms = re.search(r"Signal:\s*(BUY|SELL|HOLD)", txt, re.I)
sig = ms.group(1).upper() if ms else "HOLD"

LOW, HIGH = 45.0, 55.0
trade_sig = "SELL" if prob < LOW else "BUY" if prob > HIGH else "HOLD"
now = datetime.now(timezone.utc)
today = now.strftime("%Y-%m-%d")

# Clean duplicates from today - keep only first trade of the day
if p.exists():
    try:
        df = pd.read_csv(p)
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['timestamp']).dt.strftime("%Y-%m-%d")
            # If already have a trade today, don't add another
            if today in df['date'].values:
                print(f"Already have trade for {today} - skipping duplicate")
                # Also dedupe: keep first per day
                df = df.drop_duplicates(subset=['date'], keep='first')
                df = df.drop(columns=['date'])
                df.to_csv(p, index=False)
                print("Cleaned duplicates, kept first trade per day")
                exit(0)
            df = df.drop(columns=['date'])
    except Exception as e:
        print(f"Dedupe check failed: {e}")

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

print("paper_trade_v2 done - 1 trade per day max")
