# log_live.py - Collects 1 live EUR/USD point every 15 min
# Writes BOTH results/live_prices.csv (table) and results/live_accuracy.csv (count)
import os
import time
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

os.makedirs("results", exist_ok=True)

def get_price():
    # Try 3 times, yfinance sometimes locks
    for i in range(3):
        try:
            df = yf.download("EURUSD=X", period="1d", interval="15m", auto_adjust=True, progress=False)
            if df is None or len(df) == 0:
                raise ValueError("empty")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            return float(close.iloc[-1])
        except Exception as e:
            print(f"Attempt {i+1} failed: {e}")
            time.sleep(5)
    # Fallback: try 1h interval
    try:
        df = yf.download("EURUSD=X", period="2d", interval="1h", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return float(close.iloc[-1])
    except Exception as e:
        print(f"Fallback failed: {e}")
        return None

price = get_price()
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

if price is None:
    print("Could not fetch price - skipping this run")
    raise SystemExit(0)

print(f"Live EUR/USD: {price:.4f} at {now}")

# --- 1. Write live_prices.csv (the table your dashboard shows) ---
live_path = "results/live_prices.csv"
if os.path.exists(live_path):
    live = pd.read_csv(live_path)
else:
    live = pd.DataFrame(columns=["timestamp", "price"])

# Dedupe: don't add same timestamp twice
if len(live) == 0 or str(live.iloc[-1]["timestamp"]) != now:
    new_row = pd.DataFrame([{"timestamp": now, "price": price}])
    live = pd.concat([live, new_row], ignore_index=True)
    live.to_csv(live_path, index=False)
    print(f"Wrote {live_path}: {len(live)} points")
else:
    print("Duplicate timestamp - skipped")

# --- 2. Update live_accuracy.csv (count + trades) ---
trades = pd.DataFrame()
if os.path.exists("results/paper_trades.csv"):
    try:
        trades = pd.read_csv("results/paper_trades.csv")
    except Exception:
        pass

total_trades = len(trades)
closed = 0
wins = 0
total_pnl = 0.0
if len(trades) > 0 and "pnl" in trades.columns:
    for _, r in trades.iterrows():
        try:
            if str(r.get("status","")).upper() in ["CLOSED","WIN","LOSS","SETTLED"]:
                closed += 1
                total_pnl += float(r.get("pnl",0) or 0)
                if float(r.get("pnl",0) or 0) > 0:
                    wins += 1
        except Exception:
            pass
win_rate = (wins/closed*100) if closed>0 else 0.0

acc_path = "results/live_accuracy.csv"
if os.path.exists(acc_path):
    acc = pd.read_csv(acc_path)
else:
    acc = pd.DataFrame(columns=["timestamp","live_points","total_trades","win_rate_pct","total_pnl"])

acc_row = pd.DataFrame([{
    "timestamp": now,
    "live_points": len(live),
    "total_trades": total_trades,
    "win_rate_pct": round(win_rate,1),
    "total_pnl": round(total_pnl,2),
}])
acc = pd.concat([acc, acc_row], ignore_index=True)
acc.to_csv(acc_path, index=False)
print(f"Wrote {acc_path}: live_points={len(live)} trades={total_trades}")
