import yfinance as yf
from pathlib import Path
from datetime import datetime, timezone

try:
    ticker = yf.Ticker("EURUSD=X")
    hist = ticker.history(period="1d", interval="1m")
    price = float(hist['Close'].iloc[-1]) if not hist.empty else 0.0
except Exception as e:
    print(f"yfinance failed: {e} - using 0")
    price = 0.0

try:
    Path("results").mkdir(exist_ok=True)
    log_path = Path("results/live_log.csv")
    # create header if not exists
    if not log_path.exists():
        log_path.write_text("timestamp,price\n")
    with open(log_path, "a") as f:
        ts = datetime.now(timezone.utc).isoformat()
        f.write(f"{ts},{price:.5f}\n")
    print(f"Logged {price:.5f}")
except Exception as e:
    print(f"Log failed: {e}")

print("log_live.py done - never fails")
