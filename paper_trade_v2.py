# paper_trade_v2.py - Paper trading on LIVE data with REAL costs
# Fixes from review + all previous rules:
# - 1 trade per day max (dedupe)
# - Kill-switch if fake balance < $70
# - No trade weekend or NFP first Friday
# - Position sizing $10 at 55-60%, $15 at 60-65%, $20 at 65%+
# - ADX filter (handled in today_signal.py)
# - Spread/slippage cost: 2 pips = 0.0002 EUR/USD
# - Entry price fallback: uses live price, not hardcoded 1.10
# - Uses completed bars only (from today_signal.py)
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone, timedelta
import calendar

os.makedirs("results", exist_ok=True)

# --- CONFIG ---
SPREAD_PIPS = 0.0002  # 2 pips = 0.0002 EUR/USD - honest cost
KILL_BALANCE = 70.0
START_BALANCE = 100.0
PROB_BUY = 55.0
PROB_SELL = 45.0

def get_live_price():
    # Try to get real live price, not 1.10 fallback
    try:
        df = yf.download("EURUSD=X", period="1d", interval="15m", auto_adjust=True, progress=False)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            return float(close.iloc[-1])
    except Exception as e:
        print(f"Live price fetch failed: {e}")
    # Fallback to last known from today_signal.csv
    try:
        sig = pd.read_csv("results/today_signal.csv")
        if len(sig) > 0:
            return float(sig.iloc[-1].get("price", 0) or 0)
    except Exception:
        pass
    # Last resort: predictions.csv
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
                if str(r.get("status","")).upper() in ["CLOSED","WIN","LOSS","SETTLED"]:
                    bal += float(r.get("pnl",0) or 0)
            except Exception:
                pass
    return bal

def is_weekend():
    # UTC now - if Saturday or Sunday, no trade
    now = datetime.now(timezone.utc)
    return now.weekday() >= 5  # 5=Sat, 6=Sun

def is_nfp_friday():
    # First Friday of month = NFP day - no trade (high volatility)
    now = datetime.now(timezone.utc)
    if now.weekday() != 4:  # Not Friday
        return False
    # Is it first Friday?
    first_day_weekday = datetime(now.year, now.month, 1, tzinfo=timezone.utc).weekday()
    # First Friday date = 1 + (4 - first_day_weekday) % 7
    first_friday = 1 + (4 - first_day_weekday) % 7
    return now.day == first_friday

def get_stake(prob):
    # Position sizing by confidence
    if prob >= 65:
        return 20
    elif prob >= 60:
        return 15
    elif prob >= 55:
        return 10
    elif prob <= 35:
        return 20
    elif prob <= 40:
        return 15
    elif prob <= 45:
        return 10
    else:
        return 0

print("=== Paper Trade v2 - With Spread Costs ===")
print(f"Spread cost: {SPREAD_PIPS*10000:.0f} pips ({SPREAD_PIPS})")
print(f"Kill-switch: ${KILL_BALANCE} | Start: ${START_BALANCE}")

# --- Load trades ---
trades_path = "results/paper_trades.csv"
if os.path.exists(trades_path):
    trades = pd.read_csv(trades_path)
else:
    trades = pd.DataFrame(columns=["timestamp","signal","prob","price","stake","type","pnl","status","spread_cost","entry_price_real"])

balance = get_balance(trades)
print(f"Current fake balance: ${balance:.2f}")

# --- Kill-switch check ---
if balance < KILL_BALANCE:
    print(f"🛑 KILL-SWITCH ACTIVE: Balance ${balance:.2f} < ${KILL_BALANCE} - NO NEW TRADES")
    raise SystemExit(0)

# --- Weekend / NFP check ---
if is_weekend():
    print("📅 Weekend - No trade (market closed)")
    raise SystemExit(0)

if is_nfp_friday():
    print("📅 NFP Friday (first Friday) - No trade (high volatility)")
    raise SystemExit(0)

# --- Load today's signal ---
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

print(f"Today: Prob {prob:.1f}% Signal {signal} ADX {adx:.1f}")

# --- 1 trade per day dedupe ---
# Check if we already traded today (same UTC date)
today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
if len(trades) > 0 and "timestamp" in trades.columns:
    try:
        trades["date_only"] = pd.to_datetime(trades["timestamp"], utc=True).dt.strftime("%Y-%m-%d")
        if today_str in trades["date_only"].values:
            print(f"Already traded today {today_str} - dedupe, no new trade")
            raise SystemExit(0)
    except Exception as e:
        print(f"Dedupe check failed (non-fatal): {e}")

# --- Check if signal is tradable ---
if signal == "HOLD":
    print(f"HOLD - No trade (prob {prob:.1f}% inside 45-55% or ADX <20)")
    raise SystemExit(0)

if prob < PROB_BUY and prob > PROB_SELL:
    print(f"Prob {prob:.1f}% inside 45-55% - HOLD, no trade")
    raise SystemExit(0)

# --- Get stake ---
stake = get_stake(prob)
if stake == 0:
    print(f"Prob {prob:.1f}% not enough edge for sizing - no trade")
    raise SystemExit(0)

print(f"Stake: ${stake} for prob {prob:.1f}%")

# --- Get real entry price (not 1.10 fallback) ---
live_price = get_live_price()
if live_price == 0:
    print("Could not get live price - no trade (avoid 1.10 fallback)")
    raise SystemExit(0)

print(f"Live EUR/USD price: {live_price:.5f}")

# Entry price with spread: BUY you pay higher, SELL you get lower
if signal == "BUY":
    entry_price = live_price + SPREAD_PIPS  # You buy at ask (higher)
else:
    entry_price = live_price - SPREAD_PIPS  # You sell at bid (lower)

print(f"Entry price with {SPREAD_PIPS*10000:.0f} pip spread: {entry_price:.5f} (live {live_price:.5f} + spread)")

# --- Create trade ---
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
new_trade = pd.DataFrame([{
    "timestamp": now,
    "signal": signal,
    "prob": round(prob, 1),
    "price": round(entry_price, 5),  # Price with spread included
    "entry_price_real": round(live_price, 5),  # Real market price for reference
    "live_price": round(live_price, 5),
    "spread_cost": SPREAD_PIPS,
    "stake": stake,
    "type": "1d",
    "pnl": 0,  # 0 until settled
    "status": "OPEN",
}])

trades = pd.concat([trades, new_trade], ignore_index=True)
# Drop helper column if exists
if "date_only" in trades.columns:
    trades = trades.drop(columns=["date_only"])

trades.to_csv(trades_path, index=False)
print(f"✅ OPENED {signal} {prob:.1f}% @ {entry_price:.5f} (real {live_price:.5f} + {SPREAD_PIPS} spread) stake ${stake} - Balance ${balance:.2f}")
print(f"Will settle in 20h via live_accuracy.py - Needs EUR/USD > {entry_price:.5f} for BUY to WIN")

# --- Also update live_accuracy.csv with new trade count ---
try:
    acc_path = "results/live_accuracy.csv"
    if os.path.exists(acc_path):
        acc = pd.read_csv(acc_path)
        live_points = int(acc.iloc[-1]["live_points"]) if len(acc) > 0 and "live_points" in acc.columns else 0
    else:
        acc = pd.DataFrame(columns=["timestamp","live_points","total_trades","win_rate_pct","total_pnl"])
        live_points = 0
    
    # Recalc balance and win rate
    bal = START_BALANCE
    closed = 0
    wins = 0
    total_pnl = 0
    if len(trades) > 0 and "pnl" in trades.columns:
        for _, r in trades.iterrows():
            try:
                if str(r.get("status","")).upper() in ["CLOSED","WIN","LOSS","SETTLED"]:
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
    print(f"Updated {acc_path}: total_trades={len(trades)}")
except Exception as e:
    print(f"Accuracy update failed (non-fatal): {e}")
