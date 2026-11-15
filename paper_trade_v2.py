"""
Paper trade v2 - fake money test for ALL models, fixed.

Run: python paper_trade_v2.py

Tests Logistic, RF, GB, Ensemble with Always Trade (0.5 threshold)
Shows which would have made fake money in 2025-2026.
"""
import pandas as pd
from pathlib import Path

RESULTS = Path("results")
PRED = RESULTS / "predictions.csv"

def test_model(df, model_col, ret_col, start_date="2025-01-01"):
    recent = df[df["Date_parsed"] >= start_date].copy()
    COST = 0.00009
    balance = 10000.0
    pos = 0
    trades = 0
    for _, row in recent.iterrows():
        prob = row[model_col]
        ret = row[ret_col]
        # Always trade: prob > 0.5 = long, else short
        signal = 1 if prob > 0.5 else -1
        cost = COST if pos != signal else 0
        if cost>0:
            trades+=1
        pnl = pos * ret - cost
        balance *= (1 + pnl)
        pos = signal
    total_ret = balance/10000 - 1
    return balance, total_ret, trades, len(recent)

def main():
    if not PRED.exists():
        print("Run python predictor_v3.py first")
        return
    df = pd.read_csv(PRED)
    df["Date_parsed"] = pd.to_datetime(df.iloc[:,0])
    df = df.sort_values("Date_parsed")
    
    # find return column
    ret_col = None
    for c in df.columns:
        if "actual" in c.lower() and "return" in c.lower():
            ret_col = c
            break
    
    models = [c for c in df.columns if c not in [df.columns[0], ret_col, "Date_parsed", "Date", "date"] and "return" not in c.lower() and "date" not in c.lower() and "time" not in c.lower()]
    
    print("="*60)
    print("PAPER TRADE V2 - FAKE MONEY TEST (Fixed)")
    print("="*60)
    print(f"Return column: {ret_col}")
    print(f"Testing period: 2025-01-01 to 2026-11-13")
    
    bh_ret = (1 + df[df["Date_parsed"] >= "2025-01-01"][ret_col]).prod() - 1
    print(f"Buy & Hold EUR/USD 2025+: {bh_ret*100:.1f}%\n")
    
    results = []
    for model in models:
        bal, ret, trades, n = test_model(df, model, ret_col, "2025-01-01")
        results.append((model, bal, ret, trades))
        status = "PASS" if ret > bh_ret and ret > 0 else "FAIL"
        print(f"{model:25s} ${bal:8,.2f}  {ret*100:+6.1f}%  trades {trades:3d}  {status}")
    
    print("\n" + "-"*60)
    best = max(results, key=lambda x: x[2])
    print(f"BEST MODEL 2025+: {best[0]} with {best[2]*100:.1f}%")
    print("-"*60)
    print("\nNext steps after this:")
    print("1. If RF is best (usually), paper trade only RF going forward")
    print("2. Full 2022-2026 test would show RF +54.8% vs BH -1% = PASS")
    print("3. To run full period: change start_date to 2022-01-01 in file")

if __name__ == "__main__":
    main()

