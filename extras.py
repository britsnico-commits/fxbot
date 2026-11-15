"""
Extra data for the EUR/USD predictor: CFTC positioning, central-bank statement tone,
and a news-headline log.

Used automatically by predictor_v3.py. You can also run it on its own:
    python extras.py        # refreshes statements, CFTC data and the news log

Folders it uses (created automatically):
    statements/   one text file per central-bank statement:
                  fed_YYYY-MM-DD.txt  (downloaded automatically for FOMC dates in events.csv)
                  ecb_YYYY-MM-DD.txt  (paste the ECB statement text in by hand)
    results/      cftc_eurfx.csv, news_log.csv

Every download is best-effort: if a source is unreachable or has changed its format,
the step prints a message and the model simply runs without that data.
"""
import html
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
import requests

STATEMENTS = Path("statements")
RESULTS = Path("results")
HEADERS = {"User-Agent": "Mozilla/5.0 (research script for personal use)"}

# ------------------------------------------------------------ statement tone
# Crude hawkish-minus-dovish word count per 1000 words. It is a rough proxy,
# not a real language model: good enough to see whether tone shifts matter.
HAWK = ["elevated", "tighten", "tightening", "restrictive", "firming", "further increases",
        "upside risks", "strong", "robust", "solid", "vigilant", "highly attentive", "raise",
        "hike", "persistent", "sticky", "above target", "overheating"]
DOVE = ["accommodative", "accommodation", "easing", "ease", "cut", "lower", "reduce",
        "downside risks", "weak", "weakened", "slowed", "slowing", "patient", "cautious",
        "subdued", "moderated", "decline", "softening", "cooled", "below target"]


def _pattern(words):
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)


_HAWK, _DOVE = _pattern(HAWK), _pattern(DOVE)


def tone_score(text: str) -> float:
    words = max(len(text.split()), 1)
    return (len(_HAWK.findall(text)) - len(_DOVE.findall(text))) / words * 1000


def _clean_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    text = re.sub(r"\s+", " ", text)
    start = text.find("For release at")
    if start != -1:
        text = text[start:]
    end = text.find("Voting for the monetary policy action")
    if end != -1:
        text = text[:end]
    return text.strip()


def fetch_fomc_statements(events_path: str = "events.csv") -> None:
    """Download FOMC statements for every FOMC date in events.csv (cached)."""
    path = Path(events_path)
    if not path.exists():
        return
    STATEMENTS.mkdir(exist_ok=True)
    ev = pd.read_csv(path, parse_dates=["date"])
    ev = ev[(ev["event"] == "FOMC") & (ev["date"] <= pd.Timestamp.today())]
    new = 0
    for d in ev["date"]:
        out = STATEMENTS / f"fed_{d:%Y-%m-%d}.txt"
        if out.exists():
            continue
        url = f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{d:%Y%m%d}a.htm"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                continue
            text = _clean_html(r.text)
            if len(text) > 300:
                out.write_text(text, encoding="utf-8")
                new += 1
            time.sleep(0.5)
        except Exception:
            continue
    if new:
        print(f"Downloaded {new} new FOMC statements.")


def load_statement_tone(index: pd.DatetimeIndex) -> pd.DataFrame:
    fetch_fomc_statements()
    if not STATEMENTS.exists():
        return pd.DataFrame(index=index)
    cols = {}
    for bank in ("fed", "ecb"):
        rows = {}
        for p in STATEMENTS.glob(f"{bank}_*.txt"):
            try:
                d = pd.Timestamp(p.stem.split("_", 1)[1])
            except ValueError:
                continue
            rows[d + pd.Timedelta(days=1)] = tone_score(p.read_text(encoding="utf-8", errors="ignore"))
        if len(rows) < 3:
            continue
        s = pd.Series(rows).sort_index()
        full = s.reindex(s.index.union(index)).ffill().reindex(index)
        cols[f"{bank}_tone"] = full
        cols[f"{bank}_tone_chg"] = full.diff().where(full.diff() != 0).ffill()
        pos = np.arange(len(index))
        marker = pd.Series(np.where(full.ne(full.shift()), pos, np.nan), index=index).ffill()
        cols[f"{bank}_days_since_stmt"] = (pd.Series(pos, index=index) - marker).clip(upper=90)
    if not cols:
        print("No central-bank statements available: skipping statement tone.")
        return pd.DataFrame(index=index)
    out = pd.DataFrame(cols)
    if {"fed_tone", "ecb_tone"} <= set(out.columns):
        out["tone_gap_fed_minus_ecb"] = out["fed_tone"] - out["ecb_tone"]
    return out.fillna(0)


# ------------------------------------------------------------ CFTC positioning
CFTC_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"


def _pick(cols, prefix, side):
    c = [x for x in cols if x.startswith(prefix) and f"_{side}" in x
         and not any(b in x for b in ("spread", "change", "pct", "traders", "conc"))]
    c.sort(key=lambda x: (not x.endswith("_all"), len(x)))
    return c[0] if c else None


def load_cftc(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Weekly CFTC 'Traders in Financial Futures' positioning for Euro FX futures."""
    RESULTS.mkdir(exist_ok=True)
    start = (index[0] - pd.Timedelta(days=900)).strftime("%Y-%m-%dT00:00:00")
    params = {
        "$where": f"market_and_exchange_names like 'EURO FX - CHICAGO%' "
                  f"AND report_date_as_yyyy_mm_dd >= '{start}'",
        "$order": "report_date_as_yyyy_mm_dd", "$limit": 5000,
    }
    try:
        r = requests.get(CFTC_URL, params=params, headers=HEADERS, timeout=60)
        r.raise_for_status()
        raw = pd.DataFrame(r.json())
        if raw.empty:
            raise ValueError("no rows returned")
        raw.to_csv(RESULTS / "cftc_eurfx.csv", index=False)
    except Exception as e:
        cache = RESULTS / "cftc_eurfx.csv"
        if cache.exists():
            print(f"CFTC download failed ({str(e)[:50]}); using cached file.")
            raw = pd.read_csv(cache)
        else:
            print(f"CFTC positioning skipped: {str(e)[:70]}")
            return pd.DataFrame(index=index)

    cols = list(raw.columns)
    date_col = next((c for c in cols if c.startswith("report_date")), None)
    oi_col = next((c for c in cols if c.startswith("open_interest")), None)
    if date_col is None or oi_col is None:
        print("CFTC data format not recognised: skipping positioning.")
        return pd.DataFrame(index=index)
    raw[date_col] = pd.to_datetime(raw[date_col])
    raw = raw.drop_duplicates(date_col).set_index(date_col).sort_index()
    oi = pd.to_numeric(raw[oi_col], errors="coerce")

    out = pd.DataFrame(index=raw.index)
    for label, prefix in (("lev", "lev_money_positions"), ("assetmgr", "asset_mgr_positions"),
                          ("dealer", "dealer_positions")):
        lc, sc = _pick(cols, prefix, "long"), _pick(cols, prefix, "short")
        if lc is None or sc is None:
            continue
        net = (pd.to_numeric(raw[lc], errors="coerce") - pd.to_numeric(raw[sc], errors="coerce")) / oi
        out[f"cftc_{label}_net_pct_oi"] = net
        out[f"cftc_{label}_chg_1w"] = net.diff()
        out[f"cftc_{label}_z_3y"] = (net - net.rolling(156, min_periods=52).mean()) / \
            net.rolling(156, min_periods=52).std()
    if out.empty:
        print("CFTC columns not recognised: skipping positioning.")
        return pd.DataFrame(index=index)
    # report is as of Tuesday and published Friday evening: usable from Monday
    out.index = out.index + pd.Timedelta(days=4)
    full = out.reindex(out.index.union(index)).ffill().reindex(index)
    return full.dropna(how="all")


# ----------------------------------------------------------------- news log
FEEDS = {
    "fed_press": "https://www.federalreserve.gov/feeds/press_all.xml",
    "ecb_press": "https://www.ecb.europa.eu/rss/press.html",
    "fxstreet": "https://www.fxstreet.com/rss/news",
}


def log_news() -> None:
    """Append today's headlines (with a tone score) to results/news_log.csv.
    History builds up day by day, so it can become a backtestable feature later."""
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / "news_log.csv"
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(
        columns=["logged_at", "source", "title", "tone"])
    seen = set(zip(old["source"], old["title"]))
    rows = []
    for src, url in FEEDS.items():
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            for item in ET.fromstring(r.content).iter("item"):
                title = (item.findtext("title") or "").strip()
                if title and (src, title) not in seen:
                    rows.append({"logged_at": pd.Timestamp.now("UTC").isoformat(), "source": src,
                                 "title": title, "tone": tone_score(title)})
        except Exception:
            continue
    if rows:
        pd.concat([old, pd.DataFrame(rows)]).to_csv(path, index=False)
        print(f"News log: added {len(rows)} headlines.")
    else:
        print("News log: nothing new (or feeds unreachable).")


# ------------------------------------------------------------ event calendar
EVENT_GROUPS = {
    "fomc": ["FOMC", "FOMC_UNSCHEDULED"],
    "ecb": ["ECB", "ECB_UNSCHEDULED"],
    "nfp": ["NFP"],
    "cpi": ["US_CPI"],
}


def event_features(index: pd.DatetimeIndex, ev: pd.DataFrame, cap: int = 30) -> pd.DataFrame:
    """Per event type (FOMC, ECB, US jobs report, US CPI): is it today, days until the next
    one, days since the last one. Works for daily or hourly indexes. Calendars are public in
    advance, so using 'days to next' is not look-ahead."""
    idx = index.tz_localize(None) if getattr(index, "tz", None) is not None else index
    d = idx.values.astype("datetime64[D]")
    out = pd.DataFrame(index=index)
    any_today = np.zeros(len(index), dtype=int)
    for g, names in EVENT_GROUPS.items():
        dates = np.array(sorted(set(ev.loc[ev["event"].isin(names), "date"])), dtype="datetime64[D]")
        if len(dates) == 0:
            continue
        today = np.isin(d, dates).astype(int)
        i = np.searchsorted(dates, d, side="left")
        nxt = np.where(i < len(dates), (dates[np.minimum(i, len(dates) - 1)] - d).astype(int), cap)
        j = np.searchsorted(dates, d, side="right")
        prv = np.where(j > 0, (d - dates[np.maximum(j - 1, 0)]).astype(int), cap)
        out[f"{g}_today"] = today
        out[f"{g}_days_to"] = np.minimum(nxt, cap)
        out[f"{g}_days_since"] = np.minimum(prv, cap)
        any_today += today
    out["any_event_today"] = np.minimum(any_today, 1)
    out["events_today_count"] = any_today
    return out


# ------------------------------------------------------------------- combined
def load_all(index: pd.DatetimeIndex) -> pd.DataFrame:
    parts = [load_cftc(index), load_statement_tone(index)]
    parts = [p for p in parts if p is not None and not p.empty]
    return pd.concat(parts, axis=1) if parts else pd.DataFrame(index=index)


if __name__ == "__main__":
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=1500)
    data = load_all(idx)
    print(f"Extra features available: {list(data.columns)}")
    log_news()
