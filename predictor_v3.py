# predictor_v3.py - FOREX ONLY - FIXED VERSION
# Fixes from review:
# 1. Drops today's unfinished bar - uses only completed bars
# 2. Removes fake ecb_days_since / fed_days_since features
# 3. No BTC, Gold, DXY, Oil, SPX, VIX
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
from datetime import datetime, timezone, timedelta

os.makedirs("results", exist_ok=True)

# =========================
# Prediction audit files
# =========================
AUDIT_FILE = "results/audit_log.csv"
HISTORY_FILE = "results/prediction_history.csv"
HOLD_MOVE_THRESHOLD = 0.20

    
def check_previous_prediction(df):

    if not os.path.exists(HISTORY_FILE):
        print("\n=== DAILY AUDIT ===")
        print("No previous prediction history found.")
        return

    try:
        hist = pd.read_csv(HISTORY_FILE)

        if len(hist) == 0:
            return

        prev = hist.iloc[-1]

        prediction_bar_date = pd.to_datetime(
            prev["date"]
        ).date()

        pred_signal = str(
            prev["signal"]
        ).upper()

        dates = list(df.index.date)

        if prediction_bar_date not in dates:
            return

        idx = dates.index(prediction_bar_date)

        if idx + 1 >= len(df):
            return

        current_price = float(
            df.iloc[idx]["eurusd"]
        )

        next_price = float(
            df.iloc[idx + 1]["eurusd"]
        )

        move_pct = (
            (next_price - current_price)
            / current_price
        ) * 100

        actual_move = (
            "BUY"
            if next_price > current_price
            else "SELL"
        )

        if pred_signal == "HOLD":
            correct = abs(move_pct) < HOLD_MOVE_THRESHOLD
        else:
            correct = actual_move == pred_signal
 
        print("\n=== DAILY AUDIT ===")

        forecast_day = dates[idx + 1]

        print(
            f"Forecast for {forecast_day} | "
            f"Predicted={pred_signal} | "
            f"Actual={actual_move} | "
            f"Move={move_pct:+.3f}% | "
            f"{'✅ CORRECT' if correct else '❌ WRONG'}"
        )

        if os.path.exists(AUDIT_FILE):
            audit = pd.read_csv(AUDIT_FILE)
        else:
            audit = pd.DataFrame(
                columns=[
                    "date",
                    "predicted",
                    "actual",
                    "correct",
                    "entry_price",
                    "prob_up",
                    "move_pct"
                ]
            )

        new_row = pd.DataFrame([{
            "date": str(forecast_day),
            "predicted": pred_signal,
            "actual": actual_move,
            "correct": correct,
            "entry_price": prev["price"],
            "prob_up": prev["prob_up"],
            "move_pct": round(move_pct, 3)
        }])

        audit = pd.concat(
            [audit, new_row],
            ignore_index=True
        )

        audit.drop_duplicates(
            subset=["date"],
            keep="last",
            inplace=True
        )

        audit.to_csv(
            AUDIT_FILE,
            index=False
        )

        accuracy = (
            audit["correct"].mean()
            * 100
        )

        print(
            f"Running Accuracy: "
            f"{accuracy:.2f}% "
            f"({audit['correct'].sum()}/{len(audit)})"
        )

    except Exception as e:
        print(f"Audit error: {e}")


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

print("Downloading market data... [FOREX ONLY, COMPLETED BARS ONLY]")
data = {}
for name, ticker in TICKERS.items():
    try:
        df = yf.download(ticker, start="2018-11-19", auto_adjust=True, progress=False)
        if df is None or len(df) < 500:
            print(f"Skipped (too little data): {name}")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        data[name] = df["Close"].rename(name)
    except Exception as e:
        print(f"Skipped {name}: {e}")

if "eurusd" not in data:
    raise SystemExit("EURUSD download failed - aborting")

prices = pd.concat(data.values(), axis=1).dropna()
prices.index = pd.to_datetime(prices.index)

# --- FIX #1: DROP TODAY'S UNFINISHED BAR ---
# Only use bars where date < today UTC. Today's candle is still forming and flips signal.
today_utc = datetime.now(timezone.utc).date()
before_len = len(prices)
prices = prices[prices.index.date < today_utc]
after_len = len(prices)
print(f"{after_len} trading days (dropped {before_len-after_len} unfinished today bar), {prices.index[0].date()} to {prices.index[-1].date()}, {len(prices.columns)} forex series")
print(f"Cutoff: using only completed bars before {today_utc} UTC")
print("No FRED_API_KEY set: skipping rate differentials and macro data. [forex-only mode]")

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

eur = df["eurusd"]
ret1 = eur.pct_change()
df["ret_1"] = ret1
df["ret_5"] = eur.pct_change(5)
df["ret_20"] = eur.pct_change(20)
df["vol_60"] = ret1.rolling(60).std()
df["ma20_vs_ma50"] = eur.rolling(20).mean() / eur.rolling(50).mean() - 1
df["dist_ma20"] = eur / eur.rolling(20).mean() - 1
df["dist_ma50"] = eur / eur.rolling(50).mean() - 1
delta = eur.diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()
df["rsi_14"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
ema12 = eur.ewm(span=12, adjust=False).mean()
ema26 = eur.ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
df["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
for lag in [1, 2, 3, 5]:
    df[f"ret1_lag{lag}"] = ret1.shift(lag)
df["dow"] = df.index.dayofweek
df["month"] = df.index.month
# --- FIX #2: REMOVED FAKE ECB/FED FEATURES ---
# Old code had: df["ecb_days_since"] = (df.index.day % 30) - FAKE, removed

df["target"] = (df["eurusd"].shift(-1) > df["eurusd"]).astype(int)
# --- FIX #3: Remove last row that has bogus target (NaN > x = False -> 0) ---
# Drop last row before dropna, because its target is always 0 (future price unknown)
df = df.iloc[:-1]
df = df.dropna()

feature_cols = [c for c in df.columns if c not in ["target", "eurusd", "eurgbp", "gbpusd", "usdchf", "eurjpy", "usdjpy", "audusd", "usdcad"]]
print(f"Features: {len(feature_cols)} | usable training rows: {len(df)}")

df["is_shock"] = (df["ret_1"].abs() > 2.5 * df["vol_60"]).astype(int)
shock = df[df["is_shock"] == 1][["ret_1"]].copy()
shock.to_csv("results/shock_days.csv")
print(f"Logged {len(shock)} shock days")

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
    if proba is not None:
        conf = (proba > 0.55) | (proba < 0.45)
        conf_acc = accuracy_score(y_test[conf], preds[conf]) if conf.sum() > 0 else 0
        print(f"Accuracy {acc*100:.1f}% | majority baseline {max(y_test.mean(), 1-y_test.mean())*100:.1f}% | Confident calls: {conf.sum()} days, accuracy {conf_acc*100:.1f}%")
    else:
        print(f"Accuracy {acc*100:.1f}%")
    return acc

print("\n=== Logistic regression ===")
print(f"Test days (unseen): {len(test)}")
log = LogisticRegression(max_iter=1000, random_state=42)
log.fit(Xtr_s, y_train)
log_proba = log.predict_proba(Xte_s)[:, 1]
report("logistic", (log_proba > 0.5).astype(int), log_proba)

print("\n=== Random forest ===")
rf = RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=20, n_jobs=-1, random_state=42)
rf.fit(X_train, y_train)
rf_proba = rf.predict_proba(X_test)[:, 1]
report("rf", (rf_proba > 0.5).astype(int), rf_proba)

print("\n=== Gradient boosting ===")
gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42)
gb.fit(X_train, y_train)
gb_proba = gb.predict_proba(X_test)[:, 1]
report("gb", (gb_proba > 0.5).astype(int), gb_proba)

print("\n=== Ensemble (accuracy of ensemble, not avg of accuracies) ===")
ens_proba = (log_proba + rf_proba + gb_proba) / 3
ens_pred = (ens_proba > 0.5).astype(int)
ens_acc = accuracy_score(y_test, ens_pred)
print(f"Ensemble accuracy: {ens_acc*100:.1f}% (computed from ensemble predictions)")

importances = pd.Series(rf.feature_importances_, index=feature_cols).sort_values(ascending=False)
print("\nTop 15 features (random forest) - FOREX ONLY:")
for k, v in importances.head(15).items():
    print(f"{k:<20} {v:.4f}")

print("\nNews log: nothing new (forex-only mode)")

X_all_s = scaler.fit_transform(df[feature_cols])
log_full = LogisticRegression(max_iter=1000, random_state=42).fit(X_all_s, df["target"])
rf_full = RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=20, n_jobs=-1, random_state=42).fit(df[feature_cols], df["target"])
gb_full = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42).fit(df[feature_cols], df["target"])

last = df.iloc[[-1]][feature_cols]
last_s = scaler.transform(last)
p_log = log_full.predict_proba(last_s)[0, 1]
p_rf = rf_full.predict_proba(last)[0, 1]
p_gb = gb_full.predict_proba(last)[0, 1]
p_ens = (p_log + p_rf + p_gb) / 3

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
    "model": "FOREX_ONLY_ENSEMBLE_COMPLETED_BARS",
}])
# ===================================
# Evaluate previous prediction
# ===================================
check_previous_prediction(df)

# ===================================
# Save prediction history
# ===================================
if os.path.exists(HISTORY_FILE):

    history = pd.read_csv(HISTORY_FILE)

    duplicate = (
        history["date"].astype(str)
        == str(last_date)
    ).any()

    if not duplicate:
        history = pd.concat(
            [history, out],
            ignore_index=True
        )
else:
    history = out.copy()

history.to_csv(HISTORY_FILE, index=False)

# Latest prediction
out.to_csv(
    "results/predictions.csv",
    index=False
)
out.to_csv(
    "results/today_signal.csv",
    index=False
)

print(
    f"\nWrote results/predictions.csv: "
    f"date={last_date} "
    f"price={last_price:.4f} "
    f"prob_up={prob_up*100:.1f}% "
    f"signal={out.iloc[0]['signal']}"
)

print(
    f"Prediction history rows: "
    f"{len(history)}"
)

print(
    "FIXED: Uses only completed bars, "
    "no fake ECB/Fed features, "
    "ensemble is real ensemble accuracy."
)
