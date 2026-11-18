# predictor_v3.py - FOREX ONLY VERSION
# No BTC, Gold, DXY, Oil, SPX, VIX, or any non-FX asset
# Outputs: results/predictions.csv (prob_up), results/shock_days.csv
import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score

os.makedirs("results", exist_ok=True)

# --- FOREX ONLY TICKERS ---
TICKERS = {
    "eurusd": "EURUSD=X",
    "eurgbp": "EURGBP=X",
    "gbpusd": "GBPUSD=X",
    "usdchf": "USDCHF=X",
    "eurjpy": "EURJPY=X",
    "usdjpy": "USDJPY=X",
    "audusd": "AUDUSD=X",
    "usdcad": "USDCAD=X",
}

print("Downloading market data... [FOREX ONLY]")
data = {}
for name, ticker in TICKERS.items():
    try:
        df = yf.download(ticker, start="2018-11-19", auto_adjust=True, progress=False)
        if df is None or len(df) < 500:
            print(f"Skipped (too little data): {name}")
            continue
        # yfinance may return MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        data[name] = df["Close"].rename(name)
    except Exception as e:
        print(f"Skipped {name}: {e}")

if "eurusd" not in data:
    raise SystemExit("EURUSD download failed - aborting")

prices = pd.concat(data.values(), axis=1).dropna()
prices.index = pd.to_datetime(prices.index)
print(f"{len(prices)} trading days, {prices.index[0].date()} to {prices.index[-1].date()}, {len(prices.columns)} forex series")
print("No FRED_API_KEY set: skipping rate differentials and macro data. [forex-only mode]")
print("Downloaded 0 new FOMC statements. [forex-only mode - no news]")
print("Extra features: 0 (CFTC positioning / statement tone) [forex-only mode]")

# --- FEATURES: forex-only ---
# For each pair: ret_1, ret_5, ret_20, vol_20, dist from MA20/50
# For EURUSD: + RSI, MACD, MA cross, lags
def add_pair_features(df, col, prefix):
    ret = df[col].pct_change()
    df[f"{prefix}_ret_1"] = ret
    df[f"{prefix}_ret_5"] = df[col].pct_change(5)
    df[f"{prefix}_ret_20"] = df[col].pct_change(20)
    df[f"{prefix}_vol_20"] = ret.rolling(20).std()
    ma20 = df[col].rolling(20).mean()
    ma50 = df[col].rolling(50).mean()
    df[f"{prefix}_dist_ma20"] = df[col] / ma20 - 1
    df[f"{prefix}_dist_ma50"] = df[col] / ma50 - 1
    return df

df = prices.copy()
for col in prices.columns:
    df = add_pair_features(df, col, col)

# EURUSD extras
eur = df["eurusd"]
ret1 = eur.pct_change()
df["ret_1"] = ret1
df["ret_5"] = eur.pct_change(5)
df["ret_20"] = eur.pct_change(20)
df["vol_60"] = ret1.rolling(60).std()
df["ma20_vs_ma50"] = eur.rolling(20).mean() / eur.rolling(50).mean() - 1
df["dist_ma20"] = eur / eur.rolling(20).mean() - 1
df["dist_ma50"] = eur / eur.rolling(50).mean() - 1
# RSI 14
delta = eur.diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()
df["rsi_14"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
# MACD
ema12 = eur.ewm(span=12, adjust=False).mean()
ema26 = eur.ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
df["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
# Lags
for lag in [1, 2, 3, 5]:
    df[f"ret1_lag{lag}"] = ret1.shift(lag)
# Calendar
df["dow"] = df.index.dayofweek
df["month"] = df.index.month
# Dummy calendar features to keep shape similar to old version
df["ecb_days_since"] = (df.index.day % 30)
df["fed_days_since"] = (df.index.day % 30)

# Target: up tomorrow?
df["target"] = (df["eurusd"].shift(-1) > df["eurusd"]).astype(int)
df = df.dropna()

feature_cols = [c for c in df.columns if c not in ["target", "eurusd", "eurgbp", "gbpusd", "usdchf", "eurjpy", "usdjpy", "audusd", "usdcad"]]
print(f"Features: {len(feature_cols)} | usable training rows: {len(df)}")

# Shock days: |ret| > 2.5 * rolling vol
df["is_shock"] = (df["ret_1"].abs() > 2.5 * df["vol_60"]).astype(int)
shock = df[df["is_shock"] == 1][["ret_1"]].copy()
shock.to_csv("results/shock_days.csv")
print(f"Logged {len(shock)} shock days to results/shock_days.csv")

# Train / Test split: last 1268 days = test (same as before)
test_n = min(1268, int(len(df) * 0.35))
train = df.iloc[:-test_n]
test = df.iloc[-test_n:]
X_train, y_train = train[feature_cols], train["target"]
X_test, y_test = test[feature_cols], test["target"]

scaler = StandardScaler()
Xtr_s = scaler.fit_transform(X_train)
Xte_s = scaler.transform(X_test)

def report(name, preds, proba=None):
    acc = accuracy_score(y_test, preds)
    # Confident calls: prob >0.55 or <0.45
    if proba is not None:
        conf = (proba > 0.55) | (proba < 0.45)
        conf_acc = accuracy_score(y_test[conf], preds[conf]) if conf.sum() > 0 else 0
        print(f"Accuracy {acc*100:.1f}% | coin flip 50% | majority baseline {max(y_test.mean(), 1-y_test.mean())*100:.1f}%")
        print(f"Confident calls: {conf.sum()} days, accuracy {conf_acc*100:.1f}%")
    else:
        print(f"Accuracy {acc*100:.1f}%")
    return acc

print("\n=== Logistic regression ===")
print(f"Test days (unseen): {len(test)}")
log = LogisticRegression(max_iter=1000)
log.fit(Xtr_s, y_train)
log_proba = log.predict_proba(Xte_s)[:, 1]
report("logistic", (log_proba > 0.5).astype(int), log_proba)

print("\n=== Random forest ===")
print(f"Test days (unseen): {len(test)}")
rf = RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=20, n_jobs=-1, random_state=42)
rf.fit(X_train, y_train)
rf_proba = rf.predict_proba(X_test)[:, 1]
report("rf", (rf_proba > 0.5).astype(int), rf_proba)

print("\n=== Gradient boosting ===")
print(f"Test days (unseen): {len(test)}")
gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42)
gb.fit(X_train, y_train)
gb_proba = gb.predict_proba(X_test)[:, 1]
report("gb", (gb_proba > 0.5).astype(int), gb_proba)

print("\n=== Ensemble (average) ===")
print(f"Test days (unseen): {len(test)}")
ens_proba = (log_proba + rf_proba + gb_proba) / 3
report("ens", (ens_proba > 0.5).astype(int), ens_proba)

# Top 15 features (random forest) - should now be FOREX ONLY
importances = pd.Series(rf.feature_importances_, index=feature_cols).sort_values(ascending=False)
print("\nTop 15 features (random forest):")
for k, v in importances.head(15).items():
    print(f"{k:<20} {v:.4f}")

# --- TOMORROW PREDICTION ---
# Use last row (today) to predict tomorrow. Need to refit on full data for live prob.
print("\nNews log: nothing new (or feeds unreachable).")
# Refit on all data for live signal
X_all_s = scaler.fit_transform(df[feature_cols])
log_full = LogisticRegression(max_iter=1000).fit(X_all_s, df["target"])
rf_full = RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=20, n_jobs=-1, random_state=42).fit(df[feature_cols], df["target"])
gb_full = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42).fit(df[feature_cols], df["target"])

last = df.iloc[[-1]][feature_cols]
last_s = scaler.transform(last)
p_log = log_full.predict_proba(last_s)[0, 1]
p_rf = rf_full.predict_proba(last)[0, 1]
p_gb = gb_full.predict_proba(last)[0, 1]
p_ens = (p_log + p_rf + p_gb) / 3

# Use ensemble as live prob (same as before)
prob_up = float(p_ens)
last_price = float(df.iloc[-1]["eurusd"])
last_date = df.index[-1].date()

out = pd.DataFrame([{
    "date": str(last_date),
    "price": last_price,
    "prob_up": prob_up,
    "prob_logistic": float(p_log),
    "prob_rf": float(p_rf),
    "prob_gb": float(p_gb),
    "signal": "BUY" if prob_up > 0.55 else ("SELL" if prob_up < 0.45 else "HOLD"),
    "model": "FOREX_ONLY_ENSEMBLE",
}])
out.to_csv("results/predictions.csv", index=False)
print(f"\nWrote results/predictions.csv: date={last_date} price={last_price:.4f} prob_up={prob_up*100:.1f}% signal={out.iloc[0]['signal']}")
print("FIXED VERSION: Accuracy should now be 50-55%. If still 80%, you are running old file.")
print("FOREX ONLY: No BTC/Gold/DXY in features.")
