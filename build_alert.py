import pandas as pd
from pathlib import Path
import re

txt = Path("today_signal.txt").read_text() if Path("today_signal.txt").exists() else "No signal"
m = re.search(r"Prob UP[^0-9]*([0-9.]+)%", txt, re.I)
prob = float(m.group(1)) if m else 50.0
trade = "SELL" if prob < 45 else "BUY" if prob > 55 else "HOLD"

bal = 100
trades = 0
win = 0
if Path("results/paper_trades.csv").exists():
    try:
        df = pd.read_csv("results/paper_trades.csv")
        trades = len(df)
        closed = df[df["status"].astype(str).str.contains("CLOSED")]
        if len(closed) > 0:
            bal = 100 + float(closed["pnl"].sum())
            win = float((closed["pnl"] > 0).mean() * 100)
    except Exception as e:
        print(f"trades read failed: {e}")

live = 0
if Path("results/live_log.csv").exists():
    try:
        live = len(pd.read_csv("results/live_log.csv"))
    except:
        pass

body = f"""Today Signal: {trade} {prob}%

Fake Balance: ${bal:.2f} | Win {win:.1f}% | Trades {trades}
Live Points: {live}/2880

Dashboard: https://canictrade.streamlit.app

Signal detail:
{txt[:500]}
"""
Path("email_body.txt").write_text(body)
print(body)
print("build_alert done")
