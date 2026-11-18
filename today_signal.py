# today_signal.py - FIXED + HISTORY LOGGING
# Rule: BUY >55%, SELL <45%, else HOLD, ADX <20 forces HOLD
# Appends to results/signal_history.csv for sparkline + ADX trend
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone

os.makedirs("results", exist_ok=True)
BUY = 0.55
SELL = 0.45

def calc_adx(df, period=14):
    try:
        high = df["High"]; low = df["Low"]; close = df["Close"]
        if isinstance(high, pd.DataFrame):
            high = high.iloc[:, 0]; low = low.iloc[:, 0]; close = close.iloc[:, 0]
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        up = high - high.shift(1); down = low.shift(1) - low
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
        plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.rolling(period).mean()
        return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
    except Exception as e:
        print(f"ADX calc failed: {e}")
        return 0.0

def momentum_fallback_prob():
    try:
        df = yf.download("EURUSD=X", period="3mo", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        ret_5 = close.pct_change(5).iloc[-1] * 100
        ret_20 = close.pct_change(20).iloc[-1] * 100
        prob = 50 + (ret_5 * 2.0) + (ret_20 * 1.0)
        prob = max(40.0, min(60.0, prob))
        return float(prob), float(close.iloc[-1])
    except Exception as e:
        print(f"Momentum fallback failed: {e}")
        return 50.0, 0.0

prob = None; price = 0.0; source = ""; pred_date = ""
try:
    pred = pd.read_csv("results/predictions.csv")
    if len(pred) > 0:
        row = pred.iloc[-1]
        raw = float(row.get("prob_up", np.nan))
        if pd.isna(raw):
            raw = float(row.get("prob", np.nan))
        if not pd.isna(raw):
            prob = raw * 100 if raw <= 1.0 else raw
            price = float(row.get("price", 0))
            pred_date = str(row.get("date", ""))
            source = "PREDICTOR_FRESH"
            print(f"Loaded predictions.csv: date={pred_date} prob={prob:.1f}% price={price:.4f}")
except Exception as e:
    print(f"predictions.csv read failed: {e}")

if prob is None:
    try:
        old = pd.read_csv("results/today_signal.csv")
        if len(old) > 0:
            row = old.iloc[-1]
            prob = float(row["prob_up"])
            price = float(row.get("price", 0))
            source = f"STALE_LAST_GOOD (from {row.get('date','?')})"
            print(f"Using last good prob: {prob:.1f}% - {source}")
    except Exception as e:
        print(f"No last good signal: {e}")

if prob is None:
    prob, price = momentum_fallback_prob()
    source = "FALLBACK_MOMENTUM (no predictor file)"
    print(f"Using momentum fallback prob: {prob:.1f}%")

print("Downloading EURUSD for ADX...")
try:
    df_adx = yf.download("EURUSD=X", period="3mo", auto_adjust=True, progress=False)
    if isinstance(df_adx.columns, pd.MultiIndex):
        df_adx.columns = df_adx.columns.get_level_values(0)
    adx = calc_adx(df_adx)
    if price == 0:
        c = df_adx["Close"]
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        price = float(c.iloc[-1])
except Exception as e:
    print(f"ADX download failed: {e}")
    adx = 0.0

if prob > 55.0:
    raw_signal = "BUY"
elif prob < 45.0:
    raw_signal = "SELL"
else:
    raw_signal = "HOLD"

if adx < 20:
    final_signal = "HOLD"
    adx_note = f"CHOPPY, HOLD forced (was {raw_signal})"
else:
    final_signal = raw_signal
    adx_note = f"TRENDING, trade allowed (was {raw_signal})"

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
out = pd.DataFrame([{
    "date": now, "pred_date": pred_date, "prob_up": round(float(prob), 1),
    "prob": round(float(prob), 1), "signal": final_signal, "raw_signal": raw_signal,
    "rule": "45/55 Threshold", "adx": round(float(adx), 1), "adx_note": adx_note,
    "price": round(float(price), 4) if price else 0, "source": source,
}])
out.to_csv("results/today_signal.csv", index=False)
print(f"Prob UP Tomorrow: {prob:.1f}% Signal: {final_signal} ADX: {adx:.1f} - {adx_note}")

# --- NEW: Append to history for sparkline + ADX trend ---
try:
    hist_path = "results/signal_history.csv"
    hist_row = pd.DataFrame([{"date": now, "prob_up": round(float(prob), 1), "signal": final_signal, "raw_signal": raw_signal, "adx": round(float(adx), 1), "price": round(float(price), 4) if price else 0}])
    if os.path.exists(hist_path):
        hist = pd.read_csv(hist_path)
        # Don't double-log same day (same YYYY-MM-DD)
        today_str = now[:10]
        if len(hist) == 0 or not any(str(d)[:10] == today_str for d in hist["date"].astype(str)):
            hist = pd.concat([hist, hist_row], ignore_index=True)
            hist.to_csv(hist_path, index=False)
            print(f"Appended to {hist_path}: {len(hist)} days")
        else:
            # Update today's row with latest prob/adx
            hist.loc[hist["date"].astype(str).str[:10] == today_str, ["prob_up","signal","raw_signal","adx","price"]] = [round(float(prob),1), final_signal, raw_signal, round(float(adx),1), round(float(price),4) if price else 0]
            hist.to_csv(hist_path, index=False)
            print(f"Updated today's row in {hist_path}")
    else:
        hist_row.to_csv(hist_path, index=False)
        print(f"Created {hist_path} with 1 day")
except Exception as e:
    print(f"History log failed (non-fatal): {e}")
print("Wrote results/today_signal.csv")
