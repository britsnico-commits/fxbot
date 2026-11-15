$code = @'

"""
Paper trade with fake money - tests your predictor with all its variables.

Run: python paper_trade.py

Starts with $10,000 fake money, trades daily predictions from results/predictions.csv
Shows if it would have been profitable recently.
"""
import pandas as pd
from pathlib import Path

RESULTS = Path("results")
PRED = RESULTS / "predictions.csv"

def paper_trade():
    if not PRED.exists():
        print("Run python predictor_v3.py first")
        return
    df = pd.read_csv(PRED)
    # find columns
    ens_col = None
    ret_col = None
    date_col = None
    for c in df.columns:
        lc = c.lower()
        if "ensemble" in lc:
            ens_col = c
        if "actual" in lc and "return" in lc:
            ret_col = c
        if lc == "date":
            date_col = c
    if date_col is None:
        date_col = df.columns[0]
    if ens_col is None:
        # try second column
        candidates = [c for c in df.columns if "ensemble" in c.lower() or "average" in c.lower()]
        ens_col = candidates[0] if candidates else df.columns[1]
    if ret_col is None:
        candidates = [c for c in df.columns if "actual" in c.lower()]
        ret_col = candidates[0] if candidates else df.columns[-1]
    
    print("="*60)
    print("PAPER TRADE - FAKE MONEY TEST")
    print("="*60)
    print(f"Using {ens_col} vs {ret_col}")
    
    balance = 10000.0
    balances = []
    df["Date_parsed"] = pd.to_datetime(df[date_col])
    df = df.sort_values("Date_parsed")
    
    recent = df[df["Date_parsed"] >= "2025-01-01"].copy()
    print(f"\nTesting period: {recent['Date_parsed'].min().date()} to {recent['Date_parsed'].max().date()} ({len(recent)} days)")
    
    COST = 0.00009
    pos = 0
    trades = 0
    
    for _, row in recent.iterrows():
        prob = row[ens_col]
        ret = row[ret_col]
        signal = 1 if prob > 0.53 else -1 if prob < 0.47 else 0
        cost = 0
        if pos != signal:
            if pos != 0 and signal != 0:
                cost = COST * 2
            elif pos == 0 and signal != 0:
                cost = COST
            elif pos != 0 and signal == 0:
                cost = COST
            if cost>0:
                trades += 1
        pnl = pos * ret - cost
        balance *= (1 + pnl)
        balances.append(balance)
        pos = signal
    
    print(f"\nStarting fake money: $10,000")
    print(f"Ending fake money: ${balance:,.2f}")
    print(f"Return: {(balance/10000-1)*100:.1f}%")
    print(f"Trades: {trades}")
    
    bh_ret = (1 + recent[ret_col]).prod() - 1
    print(f"Buy & hold EUR/USD same period: {bh_ret*100:.1f}%")
    
    if balance > 10000 and balance > 10000*(1+bh_ret):
        print("\nVERDICT: PASS - beats buy & hold with fake money")
    else:
        print("\nVERDICT: FAIL - does not beat buy & hold recently")
    
    recent["fake_balance"] = balances
    recent[["Date_parsed","fake_balance"]].to_csv(RESULTS / "paper_trade_equity.csv", index=False)
    print(f"\nSaved paper_trade_equity.csv")

if __name__ == "__main__":
    paper_trade()

'@
$code | Out-File -Encoding utf8 "$HOME\OneDrive\Documents\fxbot\paper_trade.py" -Force
Write-Host "Created paper_trade.py - FAKE MONEY TEST" -ForegroundColor Green
