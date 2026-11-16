import pandas as pd
from pathlib import Path
log_path = Path("results/live_log.csv")
pred_path = Path("predictions.csv")
print("=== LIVE ACCURACY TEST ===")
if not log_path.exists():
    print("No live_log.csv yet")
else:
    df = pd.read_csv(log_path)
    print(f"Live points collected: {len(df)}")
    print(f"First: {df.iloc[0].to_dict()}")
    print(f"Last: {df.iloc[-1].to_dict()}")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    daily = df.groupby(df['timestamp'].dt.date)['price'].last().reset_index()
    daily.columns = ['date','price']
    daily['ret'] = daily['price'].pct_change()
    daily['actual_up'] = (daily['ret'] > 0).astype(int)
    print(daily.tail())
    if pred_path.exists():
        pred = pd.read_csv(pred_path)
        print(f"Predictions rows: {len(pred)}")
        print(pred.tail(3).to_string())
print("Need 20-22 days + 2880 points. >53% = keep daily, <52% = build intraday")
