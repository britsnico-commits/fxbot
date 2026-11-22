# log_accuracy.py - Check if yesterday's prediction was correct - ROOT version
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

os.makedirs("results", exist_ok=True)

ACC_PATH = "results/daily_accuracy.csv"
SIG_PATH = "results/today_signal.csv"
HIST_PATH = "results/signal_history.csv"
LIVE_PATH = "results/live_prices.csv"

def get_price_on_date(target_date):
    try:
        df = yf.download("EURUSD=X", period="10d", interval="1d", auto_adjust=True, progress=False)
        if df is not None and len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = pd.to_datetime(df.index).date
            for i in range(5):
                check_date = target_date - timedelta(days=i)
                if check_date in df.index:
                    return float(df.loc[check_date, "Close"])
    except Exception as e:
        print(f"yfinance failed: {e}")
    try:
        if os.path.exists(LIVE_PATH):
            live = pd.read_csv(LIVE_PATH)
            if len(live) > 0 and "price" in live.columns:
                live["timestamp"] = pd.to_datetime(live["timestamp"], utc=True)
                live["date"] = live["timestamp"].dt.date
                for i in range(5):
                    check_date = target_date - timedelta(days=i)
                    day_data = live[live["date"] == check_date]
                    if len(day_data) > 0:
                        return float(day_data.iloc[-1]["price"])
    except Exception as e:
        print(f"live fallback failed: {e}")
    return None

def main():
    if not os.path.exists(SIG_PATH) or not os.path.exists(HIST_PATH):
        print("No signal files yet")
        return
    sig_hist = pd.read_csv(HIST_PATH)
    if len(sig_hist) < 2:
        print(f"Only {len(sig_hist)} signals, need 2 to check accuracy")
        return
    if os.path.exists(ACC_PATH):
        acc_df = pd.read_csv(ACC_PATH)
    else:
        acc_df = pd.DataFrame(columns=["pred_date","prob_up","signal","price_then","price_now","actual_direction","predicted_direction","correct","pnl_pips"])
    
    for idx in range(len(sig_hist)-1):
        row = sig_hist.iloc[idx]
        next_row = sig_hist.iloc[idx+1]
        pred_date_str = str(row.get("date", row.get("timestamp", "")))[:10]
        if not pred_date_str:
            continue
        if len(acc_df) > 0 and pred_date_str in acc_df["pred_date"].astype(str).values:
            continue
        try:
            pred_date = datetime.strptime(pred_date_str, "%Y-%m-%d").date()
        except:
            try:
                pred_date = pd.to_datetime(pred_date_str).date()
            except:
                continue
        prob = float(row.get("prob_up", 50))
        if 0 < prob <= 1:
            prob *= 100
        signal = str(row.get("signal", "HOLD")).upper()
        price_then = float(row.get("price", 0) or 0)
        next_date_str = str(next_row.get("date", next_row.get("timestamp", "")))[:10]
        try:
            next_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
        except:
            try:
                next_date = pd.to_datetime(next_date_str).date()
            except:
                continue
        price_now = get_price_on_date(next_date)
        if price_now is None:
            price_now = float(next_row.get("price", 0) or 0)
            if price_now == 0:
                continue
        if price_then == 0:
            price_then = get_price_on_date(pred_date)
            if price_then is None:
                continue
        actual_up = price_now > price_then
        actual_direction = "UP" if actual_up else "DOWN"
        if signal == "BUY":
            predicted_direction = "UP"
            correct = actual_up
        elif signal == "SELL":
            predicted_direction = "DOWN"
            correct = not actual_up
        else:
            predicted_direction = "HOLD"
            correct = None
        pips = (price_now - price_then) * 10000
        new_entry = {
            "pred_date": pred_date_str,
            "prob_up": prob,
            "signal": signal,
            "price_then": price_then,
            "price_now": price_now,
            "actual_direction": actual_direction,
            "predicted_direction": predicted_direction,
            "correct": correct,
            "pnl_pips": pips
        }
        acc_df = pd.concat([acc_df, pd.DataFrame([new_entry])], ignore_index=True)
        print(f"Logged {pred_date_str}: {signal} {prob:.1f}% {price_then:.5f}->{price_now:.5f} {actual_direction} correct={correct}")
    acc_df.to_csv(ACC_PATH, index=False)
    print(f"Saved {len(acc_df)} records")

if __name__ == "__main__":
    main()
