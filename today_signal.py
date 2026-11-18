import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import re

# --- 1. Read Prob from predictions or predictor output ---
prob = 50.0
signal = "HOLD"

# Try predictions.csv first
p_pred = Path("predictions.csv")
p_pred2 = Path("results/predictions.csv")
pred_path = None
if p_pred.exists():
    pred_path = p_pred
elif p_pred2.exists():
    pred_path = p_pred2

if pred_path is not None:
    try:
        df = pd.read_csv(pred_path)
        # Find prob column - could be prob_up, prob, prediction etc
        prob_col = None
        for col in df.columns:
            if "prob" in col.lower() or "up" in col.lower():
                prob_col = col
                break
        if prob_col is not None and len(df) > 0:
            last_val = float(df.iloc[-1][prob_col])
            # If prob is 0-1, convert to %
            if last_val <= 1.0:
                prob = last_val * 100
            else:
                prob = last_val
            print(f"Prob from {pred_path}: {prob:.1f}%")
        else:
            # Fallback: check if df has signal column
            print(f"No prob col in {pred_path}, columns: {list(df.columns)}")
    except Exception as e:
        print(f"Predictions read failed: {e}")

# Fallback: if still 50, try reading from existing today_signal.txt or check.py output
if prob == 50.0:
    # Try to find prob in any recent file - keep 50 as HOLD
    print("Using default prob 50.0 - HOLD")

# --- 2. Apply 45/55 Rule ---
LOW, HIGH = 45.0, 55.0
if prob < LOW:
    trade_signal = "SELL"
elif prob > HIGH:
    trade_signal = "BUY"
else:
    trade_signal = "HOLD"

print(f"Rule {LOW}/{HIGH} => {trade_signal} at {prob:.1f}%")

# --- 3. ADX Regime Filter ---
adx_value = None
adx_note = ""
try:
    import yfinance as yf
    print("Calculating ADX...")
    df_adx = yf.download("EURUSD=X", period="30d", interval="1d", progress=False, auto_adjust=False)
    if isinstance(df_adx.columns, pd.MultiIndex):
        df_adx.columns = df_adx.columns.get_level_values(0)
    df_adx = df_adx.dropna()
    if len(df_adx) >= 20:
        high = df_adx['High']
        low = df_adx['Low']
        close = df_adx['Close']
        # True Range
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        # Directional Movement
        up = high - high.shift()
        down = low.shift() - low
        plus_dm = up.where((up > down) & (up > 0), 0)
        minus_dm = down.where((down > up) & (down > 0), 0)
        plus_di = 100 * (plus_dm.rolling(14).mean() / (atr + 1e-9))
        minus_di = 100 * (minus_dm.rolling(14).mean() / (atr + 1e-9))
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
        adx = dx.rolling(14).mean().iloc[-1]
        adx_value = float(adx)
        print(f"ADX: {adx_value:.1f}")
        if adx_value < 20:
            print(f"ADX {adx_value:.1f} < 20 - CHOPPY, forcing HOLD (was {trade_signal})")
            adx_note = f"ADX: {adx_value:.1f} - CHOPPY, HOLD forced (was {trade_signal})"
            trade_signal = "HOLD"
        else:
            print(f"ADX {adx_value:.1f} >= 20 - TRENDING, allow {trade_signal}")
            adx_note = f"ADX: {adx_value:.1f} - TRENDING"
    else:
        print(f"Not enough data for ADX: {len(df_adx)} rows")
except Exception as e:
    print(f"ADX filter failed: {e} - allowing trade")
    adx_note = f"ADX: failed - allowing {trade_signal}"

# --- 4. Write today_signal.txt ---
now = datetime.now(timezone.utc)
Path("results").mkdir(exist_ok=True)

content = f"""Date: {now.strftime('%Y-%m-%d %H:%M UTC')}
Prob UP Tomorrow: {prob:.1f}%
Signal: {trade_signal}
Rule: 45/55 Threshold
"""
if adx_value is not None:
    content += f"{adx_note}\n"
else:
    content += f"{adx_note}\n"

Path("today_signal.txt").write_text(content)
print(f"Wrote today_signal.txt:\n{content}")
print("today_signal.py done")
