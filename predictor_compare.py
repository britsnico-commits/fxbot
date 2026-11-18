import pandas as pd
import numpy as np
from pathlib import Path
import yfinance as yf
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import warnings
warnings.filterwarnings("ignore")

Path("results").mkdir(exist_ok=True)

# --- FOREX ONLY - No BTC, No Gold, No DXY ---
# All pairs are FX, same market, same hours
tickers = {
    "EURUSD": "EURUSD=X",
    "EURGBP": "EURGBP=X",
    "GBPUSD": "GBPUSD=X",
    "USDCHF": "USDCHF=X",
    "EURJPY": "EURJPY=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
}

print("Downloading forex-only pairs...")
data = {}
for name, ticker in tickers.items():
    try:
        df = yf.download(ticker, period="5y", interval="1d", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        data[name] = df['Close']
        print(f"{name}: {len(df)} rows")
    except Exception as e:
        print(f"{name} failed: {e}")

# Build main dataframe on EURUSD index
df = pd.DataFrame(data)
df = df.dropna()
print(f"Combined forex df: {len(df)} rows")

# --- FOREX-ONLY FEATURES ---
# Each feature is a forex pair return - 100% forex
df['eurusd_ret_1'] = df['EURUSD'].pct_change(1)
df['eurusd_ret_5'] = df['EURUSD'].pct_change(5)
df['eurusd_ret_20'] = df['EURUSD'].pct_change(20)
df['eurgbp_ret_1'] = df['EURGBP'].pct_change(1)  # EUR strength vs GBP - replaces BTC
df['gbpusd_ret_1'] = df['GBPUSD'].pct_change(1)  # GBP/USD correlation ~0.85 with EUR/USD
df['usdchf_ret_1'] = df['USDCHF'].pct_change(1)  # Inverse to EUR/USD ~-0.9
df['eurjpy_ret_1'] = df['EURJPY'].pct_change(1)  # EUR strength vs JPY
df['usdjpy_ret_1'] = df['USDJPY'].pct_change(1)  # Risk sentiment inside FX
df['audusd_ret_1'] = df['AUDUSD'].pct_change(1)  # Risk-on FX
df['usdcad_ret_1'] = df['USDCAD'].pct_change(1)  # Oil / USD strength

# Technicals from EURUSD only (still forex)
df['ma_ratio'] = df['EURUSD'] / df['EURUSD'].rolling(20).mean()
df['vol'] = df['eurusd_ret_1'].rolling(20).std()
# RSI
gain = df['eurusd_ret_1'].clip(lower=0).rolling(14).mean()
loss = df['eurusd_ret_1'].clip(upper=0).abs().rolling(14).mean()
df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))

# Target: EURUSD up tomorrow?
df['target'] = (df['EURUSD'].shift(-1) > df['EURUSD']).astype(int)

features = [
    'eurusd_ret_1','eurusd_ret_5','eurusd_ret_20',
    'eurgbp_ret_1','gbpusd_ret_1','usdchf_ret_1',
    'eurjpy_ret_1','usdjpy_ret_1','audusd_ret_1','usdcad_ret_1',
    'ma_ratio','vol','rsi'
]

df = df.dropna()
X = df[features]
y = df['target']
print(f"Features: {features}")
print(f"Training rows: {len(df)}")

split = int(len(df)*0.8)
X_train, X_test = X.iloc[:split], X.iloc[split:]
y_train, y_test = y.iloc[:split], y.iloc[split:]

results = {}

# 1. Logistic - baseline, forex only
try:
    m = LogisticRegression(max_iter=1000)
    m.fit(X_train, y_train)
    acc = m.score(X_test, y_test)
    prob = float(m.predict_proba(X.iloc[[-1]])[0][1]*100)
    results['Logistic_FX_Only'] = (acc, prob)
    print(f"Logistic FX Only acc {acc:.3f} prob {prob:.1f}%")
except Exception as e:
    print(f"Logistic failed: {e}")

# 2. XGBoost - forex only
try:
    from xgboost import XGBClassifier
    m = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, eval_metric='logloss', n_jobs=-1)
    m.fit(X_train, y_train)
    acc = m.score(X_test, y_test)
    prob = float(m.predict_proba(X.iloc[[-1]])[0][1]*100)
    results['XGBoost_FX_Only'] = (acc, prob)
    print(f"XGBoost FX Only acc {acc:.3f} prob {prob:.1f}%")
except Exception as e:
    print(f"XGBoost failed: {e}")

# 3. LightGBM - forex only
try:
    import lightgbm as lgb
    m = lgb.LGBMClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, verbose=-1)
    m.fit(X_train, y_train)
    acc = m.score(X_test, y_test)
    prob = float(m.predict_proba(X.iloc[[-1]])[0][1]*100)
    results['LightGBM_FX_Only'] = (acc, prob)
    print(f"LightGBM FX Only acc {acc:.3f} prob {prob:.1f}%")
except Exception as e:
    print(f"LightGBM failed: {e}")

# 4. Ensemble
if 'XGBoost_FX_Only' in results and 'LightGBM_FX_Only' in results:
    ens_acc = (results['XGBoost_FX_Only'][0] + results['LightGBM_FX_Only'][0]) / 2
    ens_prob = (results['XGBoost_FX_Only'][1] + results['LightGBM_FX_Only'][1]) / 2
    results['Ensemble_FX_Only'] = (ens_acc, ens_prob)
    print(f"Ensemble FX Only acc {ens_acc:.3f} prob {ens_prob:.1f}%")

# 5. Random Forest
try:
    m = RandomForestClassifier(n_estimators=200, max_depth=6, n_jobs=-1)
    m.fit(X_train, y_train)
    acc = m.score(X_test, y_test)
    prob = float(m.predict_proba(X.iloc[[-1]])[0][1]*100)
    results['RandomForest_FX_Only'] = (acc, prob)
    print(f"RF FX Only acc {acc:.3f} prob {prob:.1f}%")
except Exception as e:
    print(f"RF failed: {e}")

# Save
import csv
from datetime import datetime, timezone
p = Path("results/model_compare.csv")
is_new = not p.exists()
with open(p, "a", newline="") as f:
    w = csv.writer(f)
    if is_new:
        w.writerow(["timestamp","model","accuracy","prob_up","signal"])
    for name, (acc, prob) in results.items():
        sig = "BUY" if prob>55 else "SELL" if prob<45 else "HOLD"
        w.writerow([datetime.now(timezone.utc).isoformat(), name, round(acc,4), round(prob,1), sig])

print("predictor_compare done - FOREX ONLY, NO BTC")
