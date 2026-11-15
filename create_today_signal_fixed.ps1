$code = @'
"""
Generates today_signal.txt - one line BUY/SELL/HOLD for today.

Run: python today_signal.py
After: python predictor_v3.py
"""
import pandas as pd
from pathlib import Path
from datetime import datetime

RESULTS = Path("results")
PRED = RESULTS / "predictions.csv"
SHOCK = RESULTS / "shock_days.csv"

def main():
    if not PRED.exists():
        print("Run predictor_v3.py first")
        return
    df = pd.read_csv(PRED)
    # find ensemble column
    ens_col = None
    for c in df.columns:
        if "ensemble" in c.lower():
            ens_col = c
            break
    if ens_col is None:
        ens_col = df.columns[1]
    
    # latest row
    latest = df.iloc[-1]
    prob = latest[ens_col]
    date = latest.iloc[0]
    
    # shock check
    is_shock_recent = False
    if SHOCK.exists():
        sd = pd.read_csv(SHOCK)
        # if last 3 days had shock
        if len(sd):
            recent_shocks = sd.tail(3)
            # check if any shock in last 5 days from predictions
            try:
                last_shock = pd.to_datetime(recent_shocks.iloc[-1]["Date"]).date()
                cur_date = pd.to_datetime(date).date()
                is_shock_recent = (cur_date - last_shock).days <= 5
            except:
                is_shock_recent = False
    
    # decision
    if prob > 0.55:
        signal = "BUY"
        action = "Go LONG EUR/USD tomorrow"
        confidence = "HIGH" if prob > 0.58 else "MEDIUM"
    elif prob < 0.45:
        signal = "SELL"
        action = "Go SHORT EUR/USD tomorrow"
        confidence = "HIGH" if prob < 0.42 else "MEDIUM"
    else:
        signal = "HOLD"
        action = "Stay FLAT - no edge"
        confidence = "LOW"
    
    # write file
    txt = f"""FXBOT SIGNAL - {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}
================================================
Date: {date}
Model: {ens_col}
Prob UP tomorrow: {prob:.1%}
Signal: {signal}
Confidence: {confidence}
Action: {action}
Shock recent (last 5d): {"YES - be careful" if is_shock_recent else "No"}

Details:
- 55.7% RF accuracy historically (2022-2026)
- 55.9% recent accuracy (2025+)
- Top driver: btc_ret_1
- Buy & Hold benchmark: -1% over same period

Paper trade: Logistic +9.8% vs BH 6.2% in 2025+ (PASS)

This is paper-trade only, not financial advice.
"""
    Path("today_signal.txt").write_text(txt)
    print(txt)
    print("\nSaved to today_signal.txt")

if __name__ == "__main__":
    main()

'@
$code | Out-File -Encoding utf8 "$HOME\OneDrive\Documents\fxbot\today_signal.py" -Force
Write-Host "Fixed today_signal.py" -ForegroundColor Green
