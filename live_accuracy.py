# live_accuracy.py - Settles OPEN trades after 20h with REAL spread costs
# Fixes:
# - Entry price already includes 2 pip spread from paper_trade_v2.py
# - Win needs price > entry (which includes spread) - honest
# - Win +85% stake, Loss -stake (Deriv 1d payout)
# - Auto-settles after 20h, fetches live price at settlement time
# - Never resets live_points count
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone, timedelta

os.makedirs("results", exist_ok=True)

SPREAD_PIPS = 0.0002  # Same as paper_trade_v2.py
SETTLE_HOURS = 20
PAYOUT_PCT = 0.85  # Win = +85% of stake

def get_live_price():
    for _ in range(3):
        try:
            df = yf.download("EURUSD=X", period="1d", interval="15m", auto_adjust=True, progress=False)
            if df is None or len(df) == 0:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            return float(close.iloc[-1])
        except Exception:
            pass
    # Fallback to 1h
    try:
        df = yf.download("EURUSD=X", period="2d", interval="1h", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return float(close.iloc[-1])
    except Exception:
        return None

print("=== Live Accuracy - Settlement with Spread ===")
print(f"Spread: {SPREAD_PIPS*10000:.0f} pips | Settle after: {SETTLE_HOURS}h | Payout: +{PAYOUT_PCT*100:.0f}%")

trades_path = "results/paper_trades.csv"
if not os.path.exists(trades_path):
    print("No paper_trades.csv - nothing to settle")
    raise SystemExit(0)

trades = pd.read_csv(trades_path)
if len(trades) == 0:
    print("No trades yet")
    raise SystemExit(0)

# Ensure needed columns exist (for old trades without spread_cost)
if "spread_cost" not in trades.columns:
    trades["spread_cost"] = SPREAD_PIPS
if "entry_price_real" not in trades.columns:
    trades["entry_price_real"] = trades.get("price", 0)
if "pnl" not in trades.columns:
    trades["pnl"] = 0
if "status" not in trades.columns:
    trades["status"] = "OPEN"

now = datetime.now(timezone.utc)
settled_count = 0

for idx, row in trades.iterrows():
    try:
        status = str(row.get("status", "")).upper()
        if status != "OPEN":
            continue

        ts_str = str(row.get("timestamp", ""))
        try:
            ts = pd.to_datetime(ts_str, utc=True)
        except Exception:
            print(f"Skipping trade {idx} - bad timestamp {ts_str}")
            continue

        age_hours = (now - ts).total_seconds() / 3600
        if age_hours < SETTLE_HOURS:
            print(f"Trade {idx} age {age_hours:.1f}h < {SETTLE_HOURS}h - not yet settling")
            continue

        # --- Settle this trade ---
        live_price = get_live_price()
        if live_price is None:
            print(f"Could not fetch live price to settle trade {idx} - skipping")
            continue

        entry_price = float(row.get("price", 0) or 0)  # This already includes spread
        signal = str(row.get("signal", "BUY")).upper()
        stake = float(row.get("stake", 10) or 10)

        # Win logic: must beat entry price which already includes spread
        # For BUY: live_price > entry_price (entry = live_at_entry + spread)
        # For SELL: live_price < entry_price (entry = live_at_entry - spread)
        if signal == "BUY":
            is_win = live_price > entry_price
        else:  # SELL
            is_win = live_price < entry_price

        if is_win:
            pnl = stake * PAYOUT_PCT
            new_status = "WIN"
        else:
            pnl = -stake
            new_status = "LOSS"

        trades.at[idx, "pnl"] = round(pnl, 2)
        trades.at[idx, "status"] = new_status
        # Log settlement price
        trades.at[idx, "settle_price"] = round(live_price, 5)
        trades.at[idx, "settle_timestamp"] = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        print(f"✅ Settled trade {idx}: {signal} @ {entry_price:.5f} (real {row.get('entry_price_real',0)} + spread) -> Now {live_price:.5f} = {new_status} PnL {pnl:+.2f} (age {age_hours:.1f}h)")
        settled_count += 1

    except Exception as e:
        print(f"Error settling trade {idx}: {e}")

if settled_count > 0:
    trades.to_csv(trades_path, index=False)
    print(f"Saved {settled_count} settled trades to {trades_path}")
else:
    print("No trades settled this run")

# --- Update live_accuracy.csv ---
try:
    acc_path = "results/live_accuracy.csv"
    live_path = "results/live_prices.csv"
    
    # Get live_points count - recover if reset
    live_points = 0
    if os.path.exists(live_path):
        try:
            live_df = pd.read_csv(live_path)
            live_points = len(live_df)
        except Exception:
            pass
    
    # Recover from previous accuracy log max
    if os.path.exists(acc_path):
        try:
            acc_old = pd.read_csv(acc_path)
            if len(acc_old) > 0 and "live_points" in acc_old.columns:
                prev_max = int(acc_old["live_points"].max())
                if prev_max > live_points:
                    live_points = prev_max
        except Exception:
            pass

    # Calc totals
    total_trades = len(trades)
    closed = 0
    wins = 0
    total_pnl = 0.0
    for _, r in trades.iterrows():
        try:
            if str(r.get("status","")).upper() in ["WIN","LOSS","CLOSED","SETTLED"]:
                closed += 1
                pnl = float(r.get("pnl",0) or 0)
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
        except Exception:
            pass
    win_rate = (wins/closed*100) if closed>0 else 0.0
    balance = 100.0 + total_pnl

    # Append or update accuracy log
    if os.path.exists(acc_path):
        acc = pd.read_csv(acc_path)
    else:
        acc = pd.DataFrame(columns=["timestamp","live_points","total_trades","win_rate_pct","total_pnl","balance"])

    # Don't duplicate same minute - but always log after settlement
    now_str = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    new_row = pd.DataFrame([{
        "timestamp": now_str,
        "live_points": live_points,
        "total_trades": total_trades,
        "win_rate_pct": round(win_rate,1),
        "total_pnl": round(total_pnl,2),
        "balance": round(balance,2),
    }])
    
    # If last row has same live_points and total_trades and no settlement, skip duplicate
    if settled_count == 0 and len(acc) > 0:
        try:
            last = acc.iloc[-1]
            if int(last.get("live_points",0)) == live_points and int(last.get("total_trades",0)) == total_trades:
                print("No change in points or trades and no settlement - skipping accuracy log duplicate")
                raise SystemExit(0)
        except SystemExit:
            raise
        except Exception:
            pass

    acc = pd.concat([acc, new_row], ignore_index=True)
    acc.to_csv(acc_path, index=False)
    print(f"Wrote {acc_path}: live_points={live_points} total_trades={total_trades} closed={closed} wins={wins} win_rate={win_rate:.1f}% pnl={total_pnl:.2f} balance={balance:.2f}")

except SystemExit:
    pass
except Exception as e:
    print(f"Accuracy log update failed: {e}")

print("Done")
