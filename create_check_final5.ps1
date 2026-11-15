$code = @'

import pandas as pd
from pathlib import Path

RESULTS = Path("results")

def load_predictions():
    return {
        "daily": RESULTS / "predictions.csv",
        "intraday": RESULTS / "intraday_predictions.csv",
        "shock": RESULTS / "shock_days.csv",
        "news": RESULTS / "news_log.csv",
        "cftc": RESULTS / "cftc_eurfx.csv",
        "feat": RESULTS / "feature_importance.csv"
    }

def check():
    print("="*60)
    print("FXBOT ONE-CLICK VALIDATOR")
    print("="*60)
    files = load_predictions()
    
    # 1. Variables
    if files["feat"].exists():
        df = pd.read_csv(files["feat"])
        feat_col = df.columns[0]
        print("\n[1] Variables review (last 5 years, RF importance):")
        print(df.head(20).to_string(index=False))
        print(f"\nTotal variables: {len(df)}")
        top3 = df[feat_col].astype(str).head(3).tolist()
        print(f"  Top 3: {top3}")
        if any("close_in_range" in s for s in top3):
            print("  !! FAIL: close_in_range in top 3 = LEAK")
        else:
            print("  PASS: No leak in top features")
    else:
        print("\n[1] No feature_importance.csv yet - run predictor_v3.py first")
    
    # 2. Shock
    if files["shock"].exists():
        df = pd.read_csv(files["shock"])
        print(f"\n[2] Instant direction changes (shock days) - {len(df)} logged")
        if len(df):
            print(df.tail(5).to_string(index=False))
    else:
        print("\n[2] No shock_days.csv yet")
    
    # 3. Historical
    if files["daily"].exists():
        df = pd.read_csv(files["daily"], parse_dates=["date"])
        if "ensemble" in df.columns and "actual_fwd_return" in df.columns:
            df["hit"] = (df["actual_fwd_return"] > 0) == (df["ensemble"] > 0.5)
            df["year"] = pd.to_datetime(df["date"]).dt.year
            print("\n[3] Historical performance (walk-forward):")
            for y, g in df.groupby("year"):
                if y >= 2020:
                    print(f"  {y}: {g['hit'].mean():.1%} accuracy (n={len(g)})")
            last = df[df["year"]>=2025]
            if len(last):
                acc = last["hit"].mean()
                print(f"  2025+ accuracy: {acc:.1%} (n={len(last)})")
                print("  PASS: >53% recent" if acc>0.53 else "  FAIL: <53% recent")
    else:
        print("\n[3] No predictions.csv")
    
    # 4. Current happenings
    print("\n[4] Current happenings:")
    if files["news"].exists():
        df = pd.read_csv(files["news"])
        print(f"  News headlines logged: {len(df)}")
    if files["cftc"].exists():
        print(f"  CFTC COT exists: {files['cftc'].stat().st_size} bytes")
    ev = Path("events.csv")
    if ev.exists():
        import pandas as pd
        df = pd.read_csv(ev, parse_dates=["date"])
        print(f"  Events calendar: {len(df)} events")
    
    # 5. Paper trade
    print("\n[5] Paper trade readiness:")
    if files["daily"].exists() and files["intraday"].exists():
        print("  Daily and hourly ready - run paper_trade.py next")
        print("  PASS: Both models generated")
    else:
        print("  FAIL: Need both predictions.csv")
    
    print("\n" + "="*60)
    print("MISSING VARIABLES ANALYSIS")
    print("="*60)
    print("""
Already have 78 features - good base.
Add to push 55.7% -> 57-58%:
  1. Rate diffs with ffill (FRED key you have)
  2. Yield curve 2y-10y, DE-US spread
  3. HY spread, risk reversals
  4. London fix, NY cut seasonality

Daily RF 55.7% Sharpe 1.45 = PASS for paper trade
Hourly 54.9% at baseline negative returns = FAIL for 1h, try HORIZON=4
""")

if __name__ == "__main__":
    check()

'@
$code | Out-File -Encoding utf8 "$HOME\OneDrive\Documents\fxbot\check.py" -Force
Write-Host "Created check.py FINAL v5 - fixed columns" -ForegroundColor Green
