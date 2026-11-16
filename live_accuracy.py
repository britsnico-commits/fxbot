
import pandas as pd
from pathlib import Path

# Check live accuracy
log_path = Path("results/live_log.csv")
pred_path = Path("predictions.csv")

print("=== LIVE ACCURACY TEST ===")

if not log_path.exists():
    print("No live_log.csv yet - wait for 1 day")
    exit(0)

df = pd.read_csv(log_path)
print(f"Live points collected: {len(df)}")
if len(df) > 2:
    print(f"First: {df.iloc[0].to_dict()}")
    print(f"Last: {df.iloc[-1].to_dict()}")
    # simple daily move accuracy if enough data
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        daily = df.resample('1D', on='timestamp')['price'].last().dropna()
        if len(daily) >= 2:
            daily['ret'] = daily['price'].pct_change()
            daily['actual_up'] = (daily['ret'] > 0).astype(int)
            print(f"\nDaily returns (last 5):\n{daily.tail()}")
            # compare with predictions if exists
            if pred_path.exists():
                pred = pd.read_csv(pred_path)
                print(f"\nPredictions rows: {len(pred)}")
                print(pred.tail(3).to_string())
    except Exception as e:
        print(f"Daily calc error: {e}")

print("\n--- For 1-month decision ---")
print("Need: 20-22 trading days + 2880 15-min prices")
print("After 1 month: If live accuracy >53% AND live PnL >0, keep daily.")
print("If <52%, build intraday model (hourly 54.9% FAIL needs fix).")
print("Your bot HOLD logic protects PnL - only trades high confidence.")
