# check.py - Computes real verdict, no hardcoded PASS
import pandas as pd
import os

def check():
    if not os.path.exists("results/predictions.csv"):
        print("No predictions.csv yet")
        return
    pred = pd.read_csv("results/predictions.csv")
    if len(pred) == 0:
        print("Empty predictions")
        return
    row = pred.iloc[-1]
    prob = float(row.get("prob_up", 0))
    if prob <= 1: prob *= 100
    print(f"Last prediction: {row.get('date')} prob_up={prob:.1f}% signal={row.get('signal')} model={row.get('model')}")
    # Compute verdict from real data, not hardcoded string
    if 45 <= prob <= 55:
        print("Verdict: HOLD - No edge (45-55%)")
    elif prob > 55:
        print(f"Verdict: BUY edge {prob-50:.1f}% above random")
    else:
        print(f"Verdict: SELL edge {50-prob:.1f}% below random")
    
    # Check for stale results
    if "BTC" in str(row.get("model","")).upper() or os.path.exists("results/feature_importance.csv"):
        print("WARNING: Stale BTC-era results still in repo - delete results/")

if __name__ == "__main__":
    check()
