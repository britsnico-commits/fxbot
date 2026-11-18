import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import csv

Path("results").mkdir(exist_ok=True)

# --- 1. Auto-close OPEN paper trades that are 1 day old ---
p_trades = Path("results/paper_trades.csv")
if p_trades.exists():
    try:
        df = pd.read_csv(p_trades)
        if len(df) > 0 and 'status' in df.columns:
            # Get current price from live_log
            current_price = None
            p_live = Path("results/live_log.csv")
            if p_live.exists():
                try:
                    live = pd.read_csv(p_live)
                    if len(live) > 0 and 'price' in live.columns:
                        current_price = float(live.iloc[-1]['price'])
                except:
                    pass

            changed = False
            now = datetime.now(timezone.utc)
            for i, row in df.iterrows():
                if str(row['status']).upper() == 'OPEN':
                    try:
                        ts = pd.to_datetime(row['timestamp'])
                        age_hours = (now - ts.tz_localize('UTC') if ts.tzinfo is None else now - ts).total_seconds() / 3600
                    except:
                        age_hours = 24  # if can't parse, close it

                    # Close if > 20 hours old (1 day trade) and we have price
                    if age_hours >= 20 and current_price is not None:
                        entry = float(row['price'])
                        sig = str(row['signal']).upper()
                        stake = float(row.get('stake', 10))
                        # Deriv Rise/Fall payout ~85% win, -100% loss
                        if sig == 'BUY':
                            win = current_price > entry
                        else:  # SELL
                            win = current_price < entry

                        pnl = round(stake * 0.85, 2) if win else -stake
                        df.at[i, 'pnl'] = pnl
                        df.at[i, 'status'] = 'CLOSED_WIN' if win else 'CLOSED_LOSS'
                        print(f"Closed trade {sig} entry {entry} -> now {current_price} pnl {pnl}")
                        changed = True

            if changed:
                df.to_csv(p_trades, index=False)
                print(f"Saved {len(df)} trades after settle")
            else:
                print(f"No trades to close yet - open trades still <20h old")
    except Exception as e:
        print(f"Settle failed: {e}")

# --- 2. Live accuracy summary ---
p_live = Path("results/live_log.csv")
p_acc = Path("results/live_accuracy.csv")

live_count = 0
if p_live.exists():
    try:
        live_count = len(pd.read_csv(p_live))
    except:
        pass

# Calculate win rate from closed trades
total_pnl = 0
win_rate = 0
total_trades = 0
if p_trades.exists():
    try:
        df = pd.read_csv(p_trades)
        total_trades = len(df)
        if 'pnl' in df.columns:
            closed = df[df['status'].astype(str).str.contains('CLOSED')]
            if len(closed) > 0:
                total_pnl = float(closed['pnl'].sum())
                win_rate = float((closed['pnl'] > 0).mean() * 100)
    except:
        pass

# Append accuracy row
is_new = not p_acc.exists()
with open(p_acc, "a", newline="") as f:
    w = csv.writer(f)
    if is_new:
        w.writerow(["timestamp", "live_points", "total_trades", "win_rate_pct", "total_pnl"])
    w.writerow([datetime.now(timezone.utc).isoformat(), live_count, total_trades, round(win_rate, 1), round(total_pnl, 2)])

print(f"Live points collected: {live_count}")
print(f"Total trades: {total_trades} Win: {win_rate}% PnL: ${total_pnl}")
print("live_accuracy.py done - auto-settle complete")
