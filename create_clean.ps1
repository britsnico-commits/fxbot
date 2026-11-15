$code = @'

"""
EUR/USD next-day direction predictor, v3 FIXED - no look-ahead
"""
import os
import warnings
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
YEARS = 8
MIN_TRAIN = 500
RETRAIN_EVERY = 42
COST = 0.00009
CONFIDENT_EDGE = 0.05
SHOCK_SIGMA = 2.5
RESULTS = Path("results")
START_DATE = "2020-02-03"
MARKETS = {
    "DX-Y.NYB": "dxy", "^VIX": "vix",
    "^TNX": "us10y", "^FVX": "us5y", "^IRX": "us3m", "^TYX": "us30y",
    "^GSPC": "spx", "^IXIC": "nasdaq", "^GDAXI": "dax", "^STOXX50E": "stoxx50",
    "GC=F": "gold", "SI=F": "silver", "HG=F": "copper",
    "CL=F": "oil", "BZ=F": "brent", "NG=F": "natgas",
    "GBPUSD=X": "gbpusd", "USDJPY=X": "usdjpy", "USDCHF=X": "usdchf",
    "AUDUSD=X": "audusd", "EURGBP=X": "eurgbp", "EURJPY=X": "eurjpy",
    "BTC-USD": "btc",
}
YIELD_COLS = {"us10y", "us5y", "us3m", "us30y"}
FRED_SERIES = {
    "fed_funds": ("DFF", "D"), "ecb_depo": ("ECBDFR", "D"),
    "us2y": ("DGS2", "D"), "us10y_f": ("DGS10", "D"), "us_bei10": ("T10YIE", "D"),
    "de10y": ("IRLTLT01DEM156N", "M"),
    "us_cpi": ("CPIAUCSL", "M"), "ez_cpi": ("CP0000EZ19M086NEST", "M"),
    "us_unemp": ("UNRATE", "M"), "ez_unemp": ("LRHUTTTTEZM156S", "M"),
    "epu_us": ("USEPUINDXD", "D"), "epu_eu": ("EUEPUINDXM", "M"),
    "epu_global": ("GEPUCURRENT", "M"), "fin_stress": ("STLFSI4", "W"),
    "hy_spread": ("BAMLH0A0HYM2", "D"),
}
def load_markets() -> pd.DataFrame:
    tickers = ["EURUSD=X"] + list(MARKETS)
    raw = yf.download(tickers, period=f"{YEARS}y", interval="1d", auto_adjust=True, progress=False)
    close = raw["Close"]
    eur = pd.DataFrame({
        "eurusd": close["EURUSD=X"],
        "eur_high": raw["High"]["EURUSD=X"],
        "eur_low": raw["Low"]["EURUSD=X"],
    })
    others = close.drop(columns="EURUSD=X").rename(columns=MARKETS)
    keep = others.columns[others.isna().mean() < 0.3]
    dropped = sorted(set(others.columns) - set(keep))
    if dropped:
        print(f"Skipped (too little data): {', '.join(dropped)}")
    others = others[keep]
    price_cols = [c for c in others.columns if c not in YIELD_COLS]
    others[price_cols] = others[price_cols].where(others[price_cols] > 0)
    df = eur.join(others).dropna(subset=["eurusd"]).ffill().dropna()
    return df
def load_fred(index: pd.DatetimeIndex) -> pd.DataFrame:
    out = pd.DataFrame(index=index)
    key = os.environ.get("FRED_API_KEY")
    if not key:
        print("No FRED_API_KEY set: skipping rate differentials and macro data.")
        return out
    try:
        from fredapi import Fred
    except ImportError:
        print("fredapi not installed (pip install fredapi): skipping FRED data.")
        return out
    fred = Fred(api_key=key)
    start = index[0] - pd.Timedelta(days=500)
    for name, (sid, freq) in FRED_SERIES.items():
        try:
            s = fred.get_series(sid, observation_start=start).dropna()
            if freq == "M":
                s.index = s.index + pd.Timedelta(days=45)
            elif freq == "W":
                s.index = s.index + pd.Timedelta(days=7)
            else:
                s.index = s.index + pd.Timedelta(days=1)
            s = s[~s.index.duplicated(keep="last")]
            out[name] = s.reindex(s.index.union(index)).ffill().reindex(index)
        except Exception as e:
            print(f"FRED {sid} skipped: {str(e)[:60]}")
    return out
def load_events(index: pd.DatetimeIndex):
    path = Path("events.csv")
    if not path.exists():
        return None
    ev = pd.read_csv(path, parse_dates=["date"])
    return ev
def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + up / dn)
def days_since(flag: pd.Series, cap: int) -> pd.Series:
    pos = np.arange(len(flag))
    last = pd.Series(np.where(flag.values, pos, np.nan), index=flag.index).ffill()
    return (pd.Series(pos, index=flag.index) - last).fillna(cap).clip(upper=cap)
def build_features(df: pd.DataFrame, fred: pd.DataFrame, events, extra=None):
    px, hi, lo = df["eurusd"], df["eur_high"], df["eur_low"]
    r = px.pct_change()
    f = pd.DataFrame(index=df.index)
    # --- momentum - all lagged by 1 so we only use yesterday
    for n in (1, 2, 3, 5, 10, 20, 60):
        f[f"ret_{n}"] = px.pct_change(n).shift(1)
    for n in range(1, 6):
        f[f"ret1_lag{n}"] = r.shift(n+1)
    # --- trend
    for n in (20, 50, 200):
        f[f"dist_ma{n}"] = (px / px.rolling(n).mean() - 1).shift(1)
    f["ma20_vs_ma50"] = (px.rolling(20).mean() / px.rolling(50).mean() - 1).shift(1)
    f["zscore_50"] = ((px - px.rolling(50).mean()) / px.rolling(50).std()).shift(1)
    f["rsi_14"] = rsi(px).shift(1)
    ema12, ema26 = px.ewm(span=12).mean(), px.ewm(span=26).mean()
    macd = ema12 - ema26
    f["macd_hist"] = ((macd - macd.ewm(span=9).mean()) / px).shift(1)
    # bollinger removed - uses high/low
    # --- volatility - lagged
    f["vol_10"] = r.rolling(10).std().shift(1)
    f["vol_20"] = r.rolling(20).std().shift(1)
    f["vol_60"] = r.rolling(60).std().shift(1)
    f["vol_ratio_10_60"] = (f["vol_10"] / f["vol_60"])
    f["vol_pctile_252"] = f["vol_20"].rolling(252).rank(pct=True)
    # atr removed - uses high/low
    # REMOVED all range-based features - they leak same-day high/low and cause 80% illusion
    # Only use returns and moving averages which are strictly past closes
    # --- other markets - CRITICAL FIX: shift by 1 to avoid same-day close leak
    for c in df.columns:
        if c in ("eurusd", "eur_high", "eur_low"):
            continue
        if c in YIELD_COLS:
            f[c] = df[c].shift(1)
            for n in (1, 5, 20):
                f[f"{c}_chg_{n}"] = df[c].diff(n).shift(1)
        elif c == "vix":
            f["vix"] = df[c].shift(1)
            f["vix_chg_1"] = df[c].pct_change().shift(1)
            f["vix_chg_5"] = df[c].pct_change(5).shift(1)
            f["vix_vs_ma20"] = (df[c] / df[c].rolling(20).mean() - 1).shift(1)
        else:
            for n in (1, 5, 20):
                f[f"{c}_ret_{n}"] = df[c].pct_change(n).shift(1)
    if {"us10y", "us3m"} <= set(df.columns):
        f["curve_10y_3m"] = (df["us10y"] - df["us3m"]).shift(1)
    if "dxy" in df.columns:
        dr = df["dxy"].pct_change()
        f["corr_dxy_20"] = r.rolling(20).corr(dr).shift(1)
        f["corr_dxy_60"] = r.rolling(60).corr(dr).shift(1)
    if "spx" in df.columns:
        f["corr_spx_20"] = r.rolling(20).corr(df["spx"].pct_change()).shift(1)
    if {"gold", "oil"} <= set(df.columns):
        f["gold_oil_ratio"] = (df["gold"] / df["oil"]).shift(1)
    if not fred.empty:
        fr = fred.reindex(df.index).ffill().shift(1)
        for c in fr.columns:
            f[f"fred_{c}"] = fr[c]
            f[f"fred_{c}_chg_20"] = fr[c].diff(20)
        if {"fed_funds", "ecb_depo"} <= set(fr.columns):
            f["policy_rate_spread"] = fr["fed_funds"] - fr["ecb_depo"]
            f["policy_spread_chg_60"] = f["policy_rate_spread"].diff(60)
        if {"us10y_f", "de10y"} <= set(fr.columns):
            f["yield_spread_10y"] = fr["us10y_f"] - fr["de10y"]
        if "us2y" in fr.columns and "us10y_f" in fr.columns:
            f["curve_10y_2y"] = fr["us10y_f"] - fr["us2y"]
        if {"us_cpi", "ez_cpi"} <= set(fr.columns):
            f["cpi_yoy_gap"] = fr["us_cpi"].pct_change(250) - fr["ez_cpi"].pct_change(250)
        if {"us_unemp", "ez_unemp"} <= set(fr.columns):
            f["unemp_gap"] = fr["us_unemp"] - fr["ez_unemp"]
    if extra is not None and not extra.empty:
        ex = extra.reindex(df.index.union(extra.index)).ffill().reindex(df.index).shift(1)
        for c in ex.columns:
            f[c] = ex[c]
    idx = df.index.to_series()
    f["dow"] = df.index.dayofweek
    f["month"] = df.index.month
    f["tdays_to_month_end"] = np.minimum(idx.groupby([idx.dt.year, idx.dt.month]).cumcount(ascending=False), 5)
    f["nfp_day"] = ((df.index.dayofweek == 4) & (df.index.day <= 7)).astype(int)
    if events is not None and extras is not None:
        # event features are public calendar, safe, but also lag to be safe
        evf = extras.event_features(df.index, events).shift(1)
        f = f.join(evf)
    shock = r.abs() > SHOCK_SIGMA * r.rolling(60).std().shift(1)
    f["shock_lag1"] = shock.shift(1).fillna(False).astype(int)
    f["days_since_shock"] = days_since(shock, 60).shift(1).fillna(60)
    f["shocks_last_60"] = shock.fillna(False).astype(int).rolling(60).sum().shift(1).fillna(0)
    f = f.replace([np.inf, -np.inf], np.nan).dropna()
    if START_DATE:
        f = f.loc[START_DATE:]
    # r is today's return, f is yesterday's features - perfect for predicting today from yesterday
    next_ret = r.reindex(f.index)
    train = next_ret.notna()
    aux = pd.DataFrame({"shock": shock.reindex(f.index), "vol_20": f["vol_20"]})
    return f[train], next_ret[train], f[~train].tail(1), aux[train]
def make_logit():
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=2000))
def make_rf():
    return RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=30, max_features="sqrt", random_state=42, n_jobs=-1)
def make_hgb():
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, l2_regularization=1.0, min_samples_leaf=40, random_state=42)
MODELS = {"Logistic regression": make_logit, "Random forest": make_rf, "Gradient boosting": make_hgb}
def walk_forward(X, ret, make_model) -> pd.Series:
    y = (ret > 0).astype(int)
    probs = pd.Series(index=X.index, dtype=float)
    for start in range(MIN_TRAIN, len(X), RETRAIN_EVERY):
        end = min(start + RETRAIN_EVERY, len(X))
        m = make_model()
        m.fit(X.iloc[:start], y.iloc[:start])
        probs.iloc[start:end] = m.predict_proba(X.iloc[start:end])[:, 1]
    return probs.dropna()
def strategy(p, ret, edge=0.0):
    sig = np.where(p > 0.5 + edge, 1, np.where(p < 0.5 - edge, -1, 0))
    pos = pd.Series(sig, index=p.index)
    turnover = pos.diff().abs().fillna(abs(pos.iloc[0]))
    return pos * ret - COST * turnover, pos
def perf(pnl):
    sd = pnl.std()
    sharpe = pnl.mean() / sd * np.sqrt(252) if sd > 0 else float("nan")
    eq = pnl.cumsum()
    return pnl.sum(), sharpe, (eq - eq.cummax()).min()
def report(name, p, ret, aux):
    ret = ret.loc[p.index]
    aux = aux.loc[p.index]
    pred_up, actual_up = p > 0.5, ret > 0
    hits = pred_up == actual_up
    n = len(p)
    base = max(actual_up.mean(), 1 - actual_up.mean())
    from scipy.stats import binomtest
    pval = binomtest(int(hits.sum()), n, 0.5, alternative="greater").pvalue
    print(f"\n=== {name} ===")
    print(f"Test days (unseen): {n}")
    print(f"Accuracy {hits.mean():.1%} | coin flip 50% | majority baseline {base:.1%} | p-value {pval:.3f}")
    conf = (p - 0.5).abs() > CONFIDENT_EDGE
    if conf.sum():
        print(f"Confident calls: {conf.sum()} days, accuracy {hits[conf].mean():.1%}")
    vol_hi = aux["vol_20"] > aux["vol_20"].expanding().median()
    print(f"Accuracy in high-vol periods {hits[vol_hi].mean():.1%} | low-vol {hits[~vol_hi].mean():.1%}")
    sh = aux["shock"].astype(bool)
    if sh.sum():
        print(f"Accuracy on shock days {hits[sh].mean():.1%} ({sh.sum()} days) | normal {hits[~sh].mean():.1%}")
    by_year = hits.groupby(hits.index.year).agg(["mean", "count"])
    print("By year: " + ", ".join(f"{y}: {m:.1%} (n={int(c)})" for y, (m, c) in by_year.iterrows()))
    for label, edge in (("Always trade", 0.0), ("Confident only", CONFIDENT_EDGE)):
        pnl, pos = strategy(p, ret, edge)
        tot, sharpe, dd = perf(pnl)
        print(f"{label:15s} return {tot:7.1%} | Sharpe {sharpe:5.2f} | max drawdown {dd:6.1%} | trades {int((pos.diff().abs() > 0).sum())}")
    print(f"Buy & hold EUR/USD over same period: {ret.sum():.1%}")
def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    print("Downloading market data...")
    df = load_markets()
    print(f"{len(df)} trading days, {df.index[0].date()} to {df.index[-1].date()}, {df.shape[1] - 3} extra market series")
    fred = load_fred(df.index)
    events = load_events(df.index)
    if events is None:
        print("No events.csv found: skipping event-calendar features.")
    extra = extras.load_all(df.index) if extras else None
    if extra is not None and not extra.empty:
        print(f"Extra features: {len(extra.columns)} (CFTC positioning / statement tone)")
    X, ret, latest, aux = build_features(df, fred, events, extra)
    print(f"Features: {X.shape[1]} | usable training rows: {len(X)}")
    r = df["eurusd"].pct_change()
    shocks = aux[aux["shock"]].index
    log = pd.DataFrame({"eurusd_move": r.reindex(shocks)})
    for c in ("dxy", "vix", "us10y", "spx", "gold"):
        if c in df.columns:
            log[f"{c}_move"] = (df[c].diff() if c in YIELD_COLS else df[c].pct_change()).reindex(shocks)
    log.reindex(log["eurusd_move"].abs().sort_values(ascending=False).index).to_csv(RESULTS / "shock_days.csv")
    print(f"Logged {len(shocks)} shock days to results/shock_days.csv")
    all_probs = {}
    for name, maker in MODELS.items():
        all_probs[name] = walk_forward(X, ret, maker)
        report(name, all_probs[name], ret, aux)
    idx = all_probs["Logistic regression"].index
    ens = pd.concat([all_probs[k].reindex(idx) for k in all_probs], axis=1).mean(axis=1)
    all_probs["Ensemble (average)"] = ens
    report("Ensemble (average)", ens, ret, aux)
    out = pd.DataFrame(all_probs)
    out["actual_next_return"] = ret.reindex(out.index)
    out.to_csv(RESULTS / "predictions.csv")
    plt.figure(figsize=(10, 5))
    r_test = ret.loc[ens.index]
    for label, edge in (("Ensemble, always trade", 0.0), ("Ensemble, confident only", CONFIDENT_EDGE)):
        plt.plot(strategy(ens, r_test, edge)[0].cumsum(), label=label)
    plt.plot(r_test.cumsum(), label="Buy & hold EUR/USD", alpha=0.6)
    plt.title("Out-of-sample cumulative return (after costs) - FIXED no lookahead")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(RESULTS / "equity_curve.png", dpi=120)
    y_all = (ret > 0).astype(int)
    rf = make_rf().fit(X, y_all)
    imp = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)
    imp.to_csv(RESULTS / "feature_importance.csv", header=["importance"])
    print("\nTop 15 features (random forest):")
    print(imp.head(15).round(4).to_string())
    if len(latest):
        calls = {n: float(m().fit(X, y_all).predict_proba(latest)[:, 1][0]) for n, m in MODELS.items()}
        avg = np.mean(list(calls.values()))
        print(f"\nLatest data: {latest.index[0].date()} -> probability EUR/USD rises next day")
        for n, v in calls.items():
            print(f"  {n}: {v:.1%}")
        print(f"  Ensemble: {avg:.1%}   (paper-trade only; not financial advice)")
    if extras:
        extras.log_news()
    print("\nFIXED VERSION: Accuracy should now be 50-55%. If still 80%, you are running old file.")
if __name__ == "__main__":
    main()

'@
$code | Out-File -Encoding utf8 "$HOME\OneDrive\Documents\fxbot\predictor_v3.py" -Force
Write-Host "Created CLEAN predictor_v3.py - no range features" -ForegroundColor Green
dir "$HOME\OneDrive\Documents\fxbot\predictor_v3.py"
