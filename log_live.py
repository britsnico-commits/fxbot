import yfinance as yf, pandas as pd
from pathlib import Path
from datetime import datetime, timezone
try:
    p=yf.Ticker('EURUSD=X').history(period='1d', interval='1m')['Close'].iloc[-1]
except:
    p=0
Path('results/live_log.csv').parent.mkdir(exist_ok=True)
with open('results/live_log.csv','a') as f:
    f.write(f\"{datetime.now(timezone.utc).isoformat()},{p:.5f}\n\")
print(f'Logged {p}')
