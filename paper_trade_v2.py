# paper_trade_v2.py - With Equity % + Spread + 3-Day Auto-Reset
# If balance < $70 for 3 days with no OPEN trades, reset to $100 and continue test
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone, timedelta

os.makedirs("results", exist_ok=True)

SPREAD_PIPS = 0.0002
KILL_BALANCE = 70.0
START_BALANCE = 100.0
RESET_DAYS = 3  # Days dead before auto-reset

def get_live_price():
    try:
        df = yf.download("EURUSD=X", period="1d", interval="15m", auto_adjust=True, progress=False)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            c = df["Close"]
            if isinstance(c, pd.DataFrame):
                c = c.iloc[:, 0]
            return float(c.iloc[-1])
    except Exception:
        pass
    try:
        sig = pd.read_csv("results/today_signal.csv")
        if len(sig) > 0:
            return float(sig.iloc[-1].get("price", 0) or 0)
    except Exception:
        pass
    try:
        pred = pd.read_csv("results/predictions.csv")
        if len(pred) > 0:
            return float(pred.iloc[-1].get("price", 0) or 0)
    except Exception:
        pass
    return 0.0

def get_balance(trades):
    bal = START_BALANCE
    if len(trades) > 0 and "pnl" in trades.columns:
        for _, r in trades.iterrows():
            try:
                if str(r.get("status","")).upper() in ["WIN","LOSS","CLOSED","SETTLED","RESET"]:
                    bal += float(r.get("pnl",0) or 0)
            except Exception:
                pass
    return bal

def has_open_trades(trades):
    if len(trades) == 0:
        return False
    for _, r in trades.iterrows():
        if str(r.get("status","")).upper() == "OPEN":
            return True
    return False

def days_since_last_trade(trades):
    if len(trades) == 0:
        return 999
    try:
        last_ts = pd.to_datetime(trades.iloc[-1]["timestamp"], utc=True)
        now = datetime.now(timezone.utc)
        return (now - last_ts).days
    except Exception:
        return 999

def is_weekend():
    return datetime.now(timezone.utc).weekday() >= 5

def is_nfp_friday():
    now = datetime.now(timezone.utc)
    if now.weekday() != 4:
        return False
    first_day_weekday = datetime(now.year, now.month, 1, tzinfo=timezone.utc).weekday()
    first_friday = 1 + (4 - first_day_weekday) % 7
    return now.day == first_friday

def get_stake_equity(prob, balance):
    if prob >= 65:
        pct = 0.20
    elif prob >= 60:
        pct = 0.15
    elif prob >= 55:
        pct = 0.10
    elif prob <= 35:
        pct = 0.20
    elif prob <= 40:
        pct = 0.15
    elif prob <= 45:
        pct = 0.10
    else:
        return 0
    stake = balance * pct
    stake = max(5, min(25, round(stake, 0)))
    return int(stake)

print(f"=== Paper Trade v2 - Equity % + Spread + {RESET_DAYS}-Day Auto-Reset ===")

trades_path = "results/paper_trades.csv"
if os.path.exists(trades_path):
    trades = pd.read_csv(trades_path)
else:
    trades = pd.DataFrame(
        columns=[
            "timestamp",
            "signal",
            "prob",
            "price",
            "stake",
            "type",
            "pnl",
            "status",
            "spread_cost",
            "entry_price_real"
        ]
    )

    trades.to_csv(trades_path, index=False)

balance = get_balance(trades)
print(f"Current balance: ${balance:.2f} | Open trades: {has_open_trades(trades)} | Days since last: {days_since_last_trade(trades)}")

# --- AUTO-RESET LOGIC ---
if balance < KILL_BALANCE:
    if not has_open_trades(trades):
        days_dead = days_since_last_trade(trades)
        if days_dead >= RESET_DAYS:
            # Reset to $100
            reset_pnl = START_BALANCE - balance
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            reset_trade = pd.DataFrame([{
                "timestamp": now,
                "signal": "RESET",
                "prob": 0,
                "price": 0,
                "entry_price_real": 0,
                "live_price": 0,
                "spread_cost": 0,
                "stake": 0,
                "type": "RESET",
                "pnl": round(reset_pnl, 2),
                "status": "RESET",
            }])
            trades = pd.concat([trades, reset_trade], ignore_index=True)
            trades.to_csv(trades_path, index=False)
            print(f"🔄 AUTO-RESET: Balance ${balance:.2f} < ${KILL_BALANCE} for {days_dead} days, no OPEN trades. Resetting to ${START_BALANCE:.2f} with PnL ${reset_pnl:+.2f}")
            balance = START_BALANCE
            # Continue to try trading today after reset
        else:
            print(f"🛑 KILL-SWITCH: Balance ${balance:.2f} < ${KILL_BALANCE}, no OPEN, {days_dead} days dead. Will auto-reset after {RESET_DAYS} days (in {RESET_DAYS - days_dead} days)")
            raise SystemExit(0)
    else:
        print(f"🛑 KILL-SWITCH: Balance ${balance:.2f} < ${KILL_BALANCE} but has OPEN trades — waiting for them to settle before reset")
        raise SystemExit(0)

# --- Normal checks ---
if is_weekend():
    print("📅 Weekend - No trade")
    raise SystemExit(0)

if is_nfp_friday():
    print("📅 NFP Friday - No trade")
    raise SystemExit(0)

signal_path = "results/today_signal.csv"
if not os.path.exists(signal_path):
    print("No today_signal.csv - no trade")
    raise SystemExit(0)

sig_df = pd.read_csv(signal_path)
if len(sig_df) == 0:
    print("Empty today_signal.csv - no trade")
    raise SystemExit(0)

row = sig_df.iloc[-1]
prob = float(row.get("prob_up", row.get("prob", 0)))
if 0 < prob <= 1.0:
    prob *= 100
signal = str(row.get("signal", "HOLD"))
adx = float(row.get("adx", 0) or 0)

print(f"Today: Prob {prob:.1f}% Signal {signal} ADX {adx:.1f} Balance ${balance:.2f}")

today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
if len(trades) > 0 and "timestamp" in trades.columns:
    try:
        tmp = trades.copy()
        tmp["date_only"] = pd.to_datetime(tmp["timestamp"], utc=True).dt.strftime("%Y-%m-%d")
        # Don't count RESET as trade day
        tmp_trades_only = tmp[tmp["type"] != "RESET"]
        if today_str in tmp_trades_only["date_only"].values:
            print(f"Already traded today {today_str} - dedupe")
            raise SystemExit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Dedupe check failed: {e}")

if signal == "HOLD":
    print(f"HOLD - No trade (prob {prob:.1f}% or ADX {adx:.1f})")
    raise SystemExit(0)

if prob < 55 and prob > 45:
    print(f"Prob {prob:.1f}% inside 45-55% - HOLD")
    raise SystemExit(0)

stake = get_stake_equity(prob, balance)
if stake == 0:
    print(f"Prob {prob:.1f}% no edge")
    raise SystemExit(0)

print(f"Stake: ${stake} ({stake/balance*100:.0f}% of ${balance:.2f})")

live_price = get_live_price()
if live_price == 0:
    print("No live price - no trade")
    raise SystemExit(0)

print(f"Live EUR/USD: {live_price:.5f}")

if signal == "BUY":
    entry_price = live_price + SPREAD_PIPS
else:
    entry_price = live_price - SPREAD_PIPS

print(f"Entry with spread: {entry_price:.5f}")

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
new_trade = pd.DataFrame([{
    "timestamp": now,
    "signal": signal,
    "prob": round(prob, 1),
    "price": round(entry_price, 5),
    "entry_price_real": round(live_price, 5),
    "live_price": round(live_price, 5),
    "spread_cost": SPREAD_PIPS,
    "stake": stake,
    "type": "1d",
    "pnl": 0,
    "status": "OPEN",
}])

trades = pd.concat([trades, new_trade], ignore_index=True)
if "date_only" in trades.columns:
    trades = trades.drop(columns=["date_only"])

trades.to_csv(trades_path, index=False)
print(f"✅ OPENED {signal} {prob:.1f}% @ {entry_price:.5f} stake ${stake} ({stake/balance*100:.0f}% equity) - Balance ${balance:.2f}")

# Update accuracy
try:
    acc_path = "results/live_accuracy.csv"
    if os.path.exists(acc_path):
        acc = pd.read_csv(acc_path)
        live_points = int(acc.iloc[-1]["live_points"]) if len(acc) > 0 and "live_points" in acc.columns else 0
    else:
        acc = pd.DataFrame(columns=["timestamp","live_points","total_trades","win_rate_pct","total_pnl"])
        live_points = 0
    bal = START_BALANCE; closed = 0; wins = 0; total_pnl = 0
    if len(trades) > 0 and "pnl" in trades.columns:
        for _, r in trades.iterrows():
            try:
                if str(r.get("status","")).upper() in ["WIN","LOSS","CLOSED","SETTLED","RESET"]:
                    closed += 1
                    pnl = float(r.get("pnl",0) or 0)
                    total_pnl += pnl
                    bal += pnl
                    if pnl > 0: wins += 1
            except Exception:
                pass
    win_rate = (wins/closed*100) if closed>0 else 0.0
    new_acc = pd.DataFrame([{
        "timestamp": now,
        "live_points": live_points,
        "total_trades": len(trades),
        "win_rate_pct": round(win_rate,1),
        "total_pnl": round(total_pnl,2),
    }])
    acc = pd.concat([acc, new_acc], ignore_index=True)
    acc.to_csv(acc_path, index=False)
    print(f"Updated {acc_path}")
except Exception as e:
    print(f"Accuracy update failed: {e}")
