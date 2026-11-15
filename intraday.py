"""
EUR/USD intraday (hourly) direction predictor with walk-forward testing.

Run:  python intraday.py

Data: Yahoo Finance only keeps about 2 years of hourly data. For longer history,
export hourly EUR/USD candles (e.g. from Dukascopy or your broker) to
data/eurusd_1h.csv with columns  time,open,high,low,close  (UTC times).
If that file exists it is used instead (cross-market features are then skipped).

Predicts: does EUR/USD close higher HORIZON hours from now? Tested walk-forward on
data the model has never seen, with a realistic ~1 pip cost per position change.
"""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import binomtest
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import extras
except ImportError:
    extras = None

warnings.filterwarnings("ignore")

HORIZON = 1              # hours ahead to predict (try 4 for a calmer signal)
MIN_TRAIN = 4000         # bars in the first training window (~7 months)
RETRAIN_EVERY = 1000     # retrain about every 8 weeks
COST = 0.00009           # ~1 pip per position change
CONFIDENT_EDGE = 0.03
RESULTS = Path("results")

CROSS = {"DX-Y.NYB": "dxy", "GBPUSD=X": "gbpusd", "USDJPY=X": "usdjpy", "^TNX": "us10y",
         "^GSPC": "spx", "GC=F": "gold", "CL=F": "oil", "^VIX": "vix"}


# --------------------------------------------------------------------- data
def _utc(df: pd.DataFrame) -> pd.DataFrame:
    df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
    return df.sort_index()


def _download(ticker: str) -> pd.DataFrame:
    d = yf.download(ticker, period="729d", interval="1h", auto_adjust=True, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return _utc(d)


def load_data() -> pd.DataFrame:
    csv = Path("data/eurusd_1h.csv")
    if csv.exists():
        d = pd.read_csv(csv, parse_dates=["time"], index_col="time")
        d.columns = [c.lower() for c in d.columns]
        base = _utc(d.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}))
        print(f"Using {csv}: {len(base)} hourly bars (no cross-market features).")
        return base[["Open", "High", "Low", "Close"]].dropna()

    base = _download("EURUSD=X")[["Open", "High", "Low", "Close"]].dropna()
    for t, name in CROSS.items():
        try:
            o = _download(t)["Close"].dropna().rename(name)
            if len(o) < 0.5 * len(base):
                print(f"Skipped {name}: too little hourly data")
                continue
            base = pd.merge_asof(base, o.to_frame(), left_index=True, right_index=True,
                                 direction="backward", tolerance=pd.Timedelta("72h"))
        except Exception as e:
            print(f"Skipped {name}: {str(e)[:50]}")
    print(f"{len(base)} hourly bars, {base.index[0]:%Y-%m-%d} to {base.index[-1]:%Y-%m-%d}")
    return base


# ----------------------------------------------------------------- features
def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + up / dn)


def build_features(df: pd.DataFrame, events=None):
    px, hi, lo = df["Close"], df["High"], df["Low"]
    r = px.pct_change()
    f = pd.DataFrame(index=df.index)

    for n in (1, 2, 3, 6, 12, 24, 48, 120):
        f[f"ret_{n}"] = px.pct_change(n).shift(1)
    for n in range(1, 7):
        f[f"ret1_lag{n}"] = r.shift(n+1)
    for n in (24, 120, 480):
        f[f"dist_ma{n}"] = (px / px.rolling(n).mean() - 1).shift(1)
    f["zscore_120"] = ((px - px.rolling(120).mean()) / px.rolling(120).std()).shift(1)
    f["rsi_14"] = rsi(px).shift(1)
    macd = px.ewm(span=12).mean() - px.ewm(span=26).mean()
    f["macd_hist"] = ((macd - macd.ewm(span=9).mean()) / px).shift(1)
    mid, sd = px.rolling(20).mean(), px.rolling(20).std()
    f["bollinger_pctb"] = ((px - (mid - 2 * sd)) / (4 * sd)).shift(1)

    for n in (12, 24, 120):
        f[f"vol_{n}"] = r.rolling(n).std().shift(1)
    f["vol_ratio"] = f["vol_12"] / f["vol_120"]
    f["vol_pctile"] = f["vol_24"].rolling(480).rank(pct=True).shift(1)
    tr = pd.concat([hi - lo, (hi - px.shift()).abs(), (lo - px.shift()).abs()], axis=1).max(axis=1)
    f["atr_14"] = (tr.rolling(14).mean() / px).shift(1)
    f["range_now"] = ((hi - lo) / px).shift(1)
    rng = (hi - lo).replace(0, np.nan)
    f["close_in_range"] = (((px - lo) / rng).fillna(0.5)).shift(1)
    lo14, hi14 = lo.rolling(14).min(), hi.rolling(14).max()
    f["stoch_k"] = (((px - lo14) / (hi14 - lo14).replace(0, np.nan)).fillna(0.5)).shift(1)

    # previous day's high/low and today's open: widely watched levels - lagged
    day = df.index.floor("D")
    d_hi = hi.groupby(day).max().shift(1)
    d_lo = lo.groupby(day).min().shift(1)
    f["dist_prev_day_high"] = (px / pd.Series(d_hi.reindex(day).values, index=df.index) - 1).shift(1)
    f["dist_prev_day_low"] = (px / pd.Series(d_lo.reindex(day).values, index=df.index) - 1).shift(1)
    f["dist_day_open"] = (px / df["Open"].groupby(day).transform("first") - 1).shift(1)

    # time of day / session (UTC) - these are known, no shift needed
    h = df.index.hour
    f["hour_sin"], f["hour_cos"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
    f["dow"] = df.index.dayofweek
    f["sess_asia"] = ((h >= 0) & (h < 7)).astype(int)
    f["sess_london"] = ((h >= 7) & (h < 13)).astype(int)
    f["sess_overlap"] = ((h >= 13) & (h < 16)).astype(int)
    f["sess_ny"] = ((h >= 16) & (h < 21)).astype(int)

    for c in [c for c in df.columns if c not in ("Open", "High", "Low", "Close")]:
        if c == "us10y":
            f["us10y"] = df[c].shift(1)
            for n in (1, 6, 24):
                f[f"us10y_chg_{n}"] = df[c].diff(n).shift(1)
        else:
            for n in (1, 6, 24):
                f[f"{c}_ret_{n}"] = df[c].pct_change(n).shift(1)
    if "dxy" in df.columns:
        f["corr_dxy_48"] = r.rolling(48).corr(df["dxy"].pct_change()).shift(1)

    if events is not None and extras is not None:
        f = f.join(extras.event_features(df.index, events, cap=10).shift(1))

    fwd = px.shift(-HORIZON) / px - 1
    gap_ok = (df.index.to_series().shift(-HORIZON) - df.index.to_series()) <= pd.Timedelta(hours=HORIZON + 1)
    f = f.replace([np.inf, -np.inf], np.nan).dropna()
    fwd = fwd.reindex(f.index)
    ok = fwd.notna() & gap_ok.reindex(f.index).fillna(False)
    return f[ok], fwd[ok], f[fwd.isna()].tail(1)


# ------------------------------------------------------------------- models
MODELS = {
    "Logistic regression": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.02, max_iter=2000)),
    "Random forest": lambda: RandomForestClassifier(n_estimators=200, max_depth=5, min_samples_leaf=60,
                                                    max_features="sqrt", random_state=42, n_jobs=-1),
    "Gradient boosting": lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150,
                                                                l2_regularization=2.0, min_samples_leaf=80,
                                                                random_state=42),
}


def walk_forward(X, fwd, make_model):
    y = (fwd > 0).astype(int)
    probs = pd.Series(index=X.index, dtype=float)
    for start in range(MIN_TRAIN, len(X), RETRAIN_EVERY):
        end = min(start + RETRAIN_EVERY, len(X))
        # leave HORIZON bars out of training so labels never overlap the test period
        m = make_model().fit(X.iloc[:max(start - HORIZON, 1)], y.iloc[:max(start - HORIZON, 1)])
        probs.iloc[start:end] = m.predict_proba(X.iloc[start:end])[:, 1]
    return probs.dropna()


# ------------------------------------------------------------------ results
def trade(p, fwd, edge=0.0, sessions=None):
    p, fwd = p.iloc[::HORIZON], fwd.loc[p.index].iloc[::HORIZON]   # non-overlapping trades
    sig = np.where(p > 0.5 + edge, 1, np.where(p < 0.5 - edge, -1, 0))
    if sessions is not None:
        sig = np.where(p.index.hour.isin(sessions), sig, 0)
    pos = pd.Series(sig, index=p.index)
    pnl = pos * fwd - COST * pos.diff().abs().fillna(abs(pos.iloc[0]))
    return pnl, pos


def perf(pnl):
    ann = np.sqrt(252 * 24 / HORIZON)
    sharpe = pnl.mean() / pnl.std() * ann if pnl.std() > 0 else float("nan")
    eq = pnl.cumsum()
    return pnl.sum(), sharpe, (eq - eq.cummax()).min()


def report(name, p, fwd):
    fwd = fwd.loc[p.index]
    hits = (p > 0.5) == (fwd > 0)
    n = len(p)
    base = max((fwd > 0).mean(), 1 - (fwd > 0).mean())
    pval = binomtest(int(hits.sum()), n, 0.5, alternative="greater").pvalue
    print(f"\n=== {name} ({HORIZON}h ahead) ===")
    print(f"Unseen bars: {n} | Accuracy {hits.mean():.1%} | coin flip 50% | majority {base:.1%} | p-value {pval:.3f}")
    conf = (p - 0.5).abs() > CONFIDENT_EDGE
    if conf.sum():
        print(f"Confident calls: {conf.sum()} bars, accuracy {hits[conf].mean():.1%}")
    h = hits.groupby(hits.index.hour).mean()
    best, worst = h.idxmax(), h.idxmin()
    print(f"Best hour (UTC) {best:02d}:00 at {h[best]:.1%} | worst {worst:02d}:00 at {h[worst]:.1%}")
    for label, mask in (("Asia 00-07", (0, 7)), ("London 07-13", (7, 13)),
                        ("London/NY overlap 13-16", (13, 16)), ("NY 16-21", (16, 21))):
        sel = (hits.index.hour >= mask[0]) & (hits.index.hour < mask[1])
        if sel.sum():
            print(f"  {label:25s} accuracy {hits[sel].mean():.1%} (n={sel.sum()})")
    active = list(range(7, 21))
    for label, edge, sess in (("Always trade", 0.0, None), ("Confident only", CONFIDENT_EDGE, None),
                              ("Confident, 07-21 UTC only", CONFIDENT_EDGE, active)):
        pnl, pos = trade(p, fwd, edge, sess)
        tot, sharpe, dd = perf(pnl)
        print(f"{label:26s} return {tot:7.1%} | Sharpe {sharpe:6.2f} | max DD {dd:6.1%} | "
              f"trades {int((pos.diff().abs() > 0).sum())}")


def main():
    RESULTS.mkdir(exist_ok=True)
    print("Downloading hourly data...")
    df = load_data()
    ev = pd.read_csv("events.csv", parse_dates=["date"]) if Path("events.csv").exists() else None
    X, fwd, latest = build_features(df, ev)
    print(f"Features: {X.shape[1]} | usable bars: {len(X)}")
    if len(X) <= MIN_TRAIN + RETRAIN_EVERY:
        print("Not enough hourly data for this test window: lower MIN_TRAIN or supply data/eurusd_1h.csv.")
        return
    probs = {}
    for name, maker in MODELS.items():
        probs[name] = walk_forward(X, fwd, maker)
        report(name, probs[name], fwd)
    ens = pd.concat(probs.values(), axis=1).mean(axis=1)
    probs["Ensemble (average)"] = ens
    report("Ensemble (average)", ens, fwd)

    out = pd.DataFrame(probs)
    out["actual_fwd_return"] = fwd.reindex(out.index)
    out.to_csv(RESULTS / "intraday_predictions.csv")

    y = (fwd > 0).astype(int)
    if len(latest):
        calls = {n: float(m().fit(X, y).predict_proba(latest)[:, 1][0]) for n, m in MODELS.items()}
        print(f"\nLatest bar {latest.index[0]:%Y-%m-%d %H:%M} UTC -> chance EUR/USD is higher in {HORIZON}h:")
        for n, v in calls.items():
            print(f"  {n}: {v:.1%}")
        print(f"  Ensemble: {np.mean(list(calls.values())):.1%}   (paper-trade only; not financial advice)")
    print("\nReality check: hourly EUR/USD is close to a coin flip and costs matter a lot. "
          "Treat anything above ~53% accuracy as unproven until it holds in paper trading.")


if __name__ == "__main__":
    main()

