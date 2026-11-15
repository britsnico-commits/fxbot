"""
Download long hourly EUR/USD history from Dukascopy into data/eurusd_1h.csv.
intraday.py picks that file up automatically.

Setup (once):   pip install dukascopy-python
Run:            python get_dukascopy.py

It downloads one year at a time and can be stopped and restarted: it resumes from the
last hour already saved. Prices are BID, times are UTC.
"""
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

START_YEAR = 2018
OUT = Path("data/eurusd_1h.csv")


def fetch_chunk(start: datetime, end: datetime) -> pd.DataFrame:
    """Works with the two common versions of the dukascopy-python package."""
    try:
        import dukascopy_python as dk
    except ImportError:
        raise SystemExit("Please run:  pip install dukascopy-python")

    # Version 1 style: dk.fetch(instrument, interval, offer_side, start, end)
    if hasattr(dk, "fetch") and hasattr(dk, "INTERVAL_HOUR_1"):
        from dukascopy_python.instruments import INSTRUMENT_FX_MAJORS_EUR_USD
        return dk.fetch(INSTRUMENT_FX_MAJORS_EUR_USD, dk.INTERVAL_HOUR_1, dk.OFFER_SIDE_BID, start, end)

    # Version 2 style: dk.fetch_candles(...) then dk.to_dataframe(...)
    from dukascopy_python.instruments import I_EUR_USD
    candles = dk.fetch_candles(instrument=I_EUR_USD, interval=1, time_unit=dk.TimeUnit.HOUR,
                               offer_side=dk.OfferSide.BID, start=start, end=end, version=2)
    return dk.to_dataframe(candles)


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if "timestamp" in df.columns:
        df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
    df.index.name = "time"
    if "volume" in df.columns:
        df = df[df["volume"] > 0]          # drop empty holiday/weekend bars
    return df[["open", "high", "low", "close"]].dropna()


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    old = pd.DataFrame()
    start = datetime(START_YEAR, 1, 1, tzinfo=timezone.utc)
    if OUT.exists():
        old = pd.read_csv(OUT, parse_dates=["time"], index_col="time")
        start = old.index[-1].to_pydatetime() + timedelta(hours=1)
        print(f"Resuming after {old.index[-1]}")
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    parts = [old] if len(old) else []
    while start < now:
        end = min(datetime(start.year + 1, 1, 1, tzinfo=timezone.utc), now)
        for attempt in range(3):
            try:
                chunk = tidy(fetch_chunk(start, end))
                break
            except Exception as e:
                print(f"  retry {attempt + 1} for {start:%Y}: {str(e)[:60]}")
                time.sleep(5)
        else:
            print(f"Giving up on {start:%Y}; run the script again to resume.")
            break
        print(f"{start:%Y-%m-%d} to {end:%Y-%m-%d}: {len(chunk)} hourly bars")
        parts.append(chunk)
        pd.concat(parts)[~pd.concat(parts).index.duplicated()].sort_index().to_csv(OUT)
        start = end

    if parts:
        full = pd.concat(parts)
        full = full[~full.index.duplicated()].sort_index()
        full.to_csv(OUT)
        print(f"Saved {len(full)} bars ({full.index[0]:%Y-%m-%d} to {full.index[-1]:%Y-%m-%d}) to {OUT}")


if __name__ == "__main__":
    main()
