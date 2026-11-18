import pandas as pd
import numpy as np
from pathlib import Path
import yfinance as yf
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import warnings
warnings.filterwarnings("ignore")

Path("results").mkdir(exist_ok=True)

# --- Load data same as predictor_v3 ---
try:
    df = yf.download("EURUSD=X", period="5y", interval="1d", progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    print(f"Loaded {len(df)} rows")
except Exception as e:
    print(f"Download failed: {e}")
    exit(0)

# --- Same 78-ish features as your v3 - simplified robust set ---
df['ret_1'] = df['Close'].pct_change(1)
df['ret_5'] = df['Close'].pct_change(5)
df['ret_20'] = df['Close'].pct_change(20)
df['btc_ret_1'] = df['ret_1']  # placeholder - your v3 uses BTC as top feature, keep ret_1 as proxy
df['ma5'] = df['Close'].rolling(5).mean()
df['ma20'] = df['Close'].rolling(20).mean()
df['ma_ratio'] = df['Close'] / df['ma20']
df['rsi'] = 100 - (100 / (1 + df['ret_1'].clip(lower=0).rolling(14).mean() / (df['ret_1'].clip(upper=0).abs().rolling(14).mean() + 1e-9)))
df['vol'] = df['ret_1'].rolling(20).std()
df['high_close'] = df['High'] / df['Close']
df['low_close'] = df['Low'] / df['Close']
df['target'] = (df['Close'].shift(-1) > df['Close']).astype(int)

features = ['ret_1','ret_5','ret_20','ma_ratio','rsi','vol','high_close','low_close']
df = df.dropna()
X = df[features]
y = df['target']

# Train on last 80%, test on last 20% for fair compare
split = int(len(df)*0.8)
X_train, X_test = X.iloc[:split], X.iloc[split:]
y_train, y_test = y.iloc[:split], y.iloc[split:]

results = {}

# 1. Logistic (your current baseline)
try:
    m = LogisticRegression(max_iter=1000)
    m.fit(X_train, y_train)
    acc = m.score(X_test, y_test)
    prob = float(m.predict_proba(X.iloc[[-1]])[0][1]*100)
    results['Logistic'] = (acc, prob)
    print(f"Logistic acc {acc:.3f} prob UP {prob:.1f}%")
except Exception as e:
    print(f"Logistic failed: {e}")

# 2. XGBoost
try:
    from xgboost import XGBClassifier
    m = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, eval_metric='logloss', n_jobs=-1)
    m.fit(X_train, y_train)
    acc = m.score(X_test, y_test)
    prob = float(m.predict_proba(X.iloc[[-1]])[0][1]*100)
    results['XGBoost'] = (acc, prob)
    print(f"XGBoost acc {acc:.3f} prob UP {prob:.1f}%")
except Exception as e:
    print(f"XGBoost failed: {e}")

# 3. LightGBM
try:
    import lightgbm as lgb
    m = lgb.LGBMClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, verbose=-1)
    m.fit(X_train, y_train)
    acc = m.score(X_test, y_test)
    prob = float(m.predict_proba(X.iloc[[-1]])[0][1]*100)
    results['LightGBM'] = (acc, prob)
    print(f"LightGBM acc {acc:.3f} prob UP {prob:.1f}%")
except Exception as e:
    print(f"LightGBM failed: {e}")

# 4. Ensemble XGBoost + LightGBM (best in literature)
if 'XGBoost' in results and 'LightGBM' in results:
    ens_acc = (results['XGBoost'][0] + results['LightGBM'][0]) / 2
    ens_prob = (results['XGBoost'][1] + results['LightGBM'][1]) / 2
    results['Ensemble_XGB_LGBM'] = (ens_acc, ens_prob)
    print(f"Ensemble acc {ens_acc:.3f} prob UP {ens_prob:.1f}%")

# 5. Random Forest (for regime filter)
try:
    m = RandomForestClassifier(n_estimators=200, max_depth=6, n_jobs=-1)
    m.fit(X_train, y_train)
    acc = m.score(X_test, y_test)
    prob = float(m.predict_proba(X.iloc[[-1]])[0][1]*100)
    results['RandomForest'] = (acc, prob)
    print(f"RF acc {acc:.3f} prob UP {prob:.1f}%")
except Exception as e:
    print(f"RF failed: {e}")

# Save comparison
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

print("predictor_compare done")
