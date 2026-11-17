import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import re

Path("results").mkdir(exist_ok=True)

# Read signal
txt = Path("today_signal.txt").read_text() if Path("today_signal.txt").exists() else ""
m = re.search(r"Prob UP[^0-9]*([0-9.]+)%", txt, re.I)
prob = float(m.group(1)) if m else 50.0
ms = re.search(r"Signal:\s*(BUY|SELL|HOLD)", txt, re.I)
sig = ms.group(1).upper() if ms else "HOLD"

LOW, HIGH = 45.0, 55.0
trade_sig = "SELL" if prob < LOW else "BUY" if prob > HIGH else "HOLD"

now = datetime.now(timezone.utc)
# Paper trade logic - log every run if BUY/SELL for live demo
p = Path("results/paper_trades.csv")
is_new = not p.exists()

# Simulate live price for PnL - use last live_log price
price = 1.10
pl = Path("results/live_log.csv")
if pl.exists():
    try:
        df = pd.read_csv(pl)
        if len(df)>0 and 'price' in df.columns:
            price = float(df.iloc[-1]['price'])
    except:
        pass

# Fake daily PnL: for demo, we log trade and will settle tomorrow
# For now, log 0 open, will calculate profit in live_accuracy
import csv
if trade_sig in ["BUY","SELL"]:
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["timestamp","signal","prob","price","stake","type","pnl","status"])
        # Check if already logged today
        already = False
        if not is_new:
            try:
                existing = pd.read_csv(p)
                today = now.strftime("%Y-%m-%d")
                if today in existing['timestamp'].astype(str).values:
                    already = True
            except:
                pass
        if not already:
            w.writerow([now.isoformat(), trade_sig, prob, price, 10, "1d", 0, "OPEN"])
            print(f"Paper trade logged: {trade_sig} {prob}% at {price}")
        else:
            print("Paper trade already logged today")
else:
    print(f"HOLD {prob}% - no paper trade")

print("paper_trade_v2 done")
