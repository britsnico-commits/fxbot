# app.py - CANIC FXBOT Dashboard - Improved Version
# - Win Rate, Profit Factor, Max DD, Streaks, Calendar Heatmap, Countdown
import os
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timezone, timedelta
import yfinance as yf

st.set_page_config(page_title="CANIC FXBOT", page_icon="📈", layout="wide")
st.markdown("""
<style>
.metric-card { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding:16px; border-radius:16px; color:white; margin-bottom:12px; }
.signal-buy { background: linear-gradient(135deg, #065f46 0%, #047857 100%); }
.signal-sell { background: linear-gradient(135deg, #7f1d1d 0%, #b91c1c 100%); }
.signal-hold { background: linear-gradient(135deg, #92400e 0%, #d97706 100%); }
.small { font-size:12px; opacity:0.7; }
.big { font-size:36px; font-weight:800; }
</style>
""", unsafe_allow_html=True)

# Auto-refresh every 60s
st_autorefresh = st.empty()
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60*1000, key="refresh")
except Exception:
    pass

os.makedirs("results", exist_ok=True)

def load_csv(path, default_cols=None):
    try:
        if os.path.exists(path):
            df = pd.read_csv(path)
            return df
    except Exception:
        pass
    if default_cols:
        return pd.DataFrame(columns=default_cols)
    return pd.DataFrame()

def get_live_price_chart():
    try:
        df = yf.download("EURUSD=X", period="1d", interval="15m", auto_adjust=True, progress=False)
        if df is None or len(df)==0:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return pd.DataFrame()

# --- Load data ---
today_sig = load_csv("results/today_signal.csv")
pred = load_csv("results/predictions.csv")
trades = load_csv("results/paper_trades.csv")
live_prices = load_csv("results/live_prices.csv")
live_acc = load_csv("results/live_accuracy.csv")
sig_hist = load_csv("results/signal_history.csv")

# --- Top Header ---
st.title("📈 CANIC FXBOT")
st.caption("Paper Trading on LIVE Data")
st.markdown("Forex-only • EUR/USD • 1 trade / day • 45/55 Rule • ADX Filter • Auto-refreshes every 60s 🔄")

# --- TODAY'S SIGNAL CARD ---
if len(today_sig) > 0:
    row = today_sig.iloc[-1]
    prob = float(row.get("prob_up", row.get("prob", 50)))
    if 0 < prob <= 1: prob *= 100
    price = float(row.get("price", 0) or 0)
    adx = float(row.get("adx", 0) or 0)
    signal = str(row.get("signal", "HOLD")).upper()
    source = str(row.get("source", row.get("model", "")))
    was = str(row.get("was", row.get("prev_signal", "")))
    ts = str(row.get("timestamp", row.get("date", "")))
    # Determine color
    if signal == "BUY":
        card_class = "metric-card signal-buy"
        emoji = "🟢"
    elif signal == "SELL":
        card_class = "metric-card signal-sell"
        emoji = "🔴"
    else:
        card_class = "metric-card signal-hold"
        emoji = "🟡"
    adx_label = "TRENDING ✅" if adx >= 20 else "CHOPPY ⚠️"
    lean = "Lean UP" if prob > 50 else "Lean DOWN" if prob < 50 else "No Edge"
    if 45 <= prob <= 55:
        lean = "No Edge"
else:
    prob = 0.0; price=0.0; adx=0.0; signal="HOLD"; source=""; was=""; ts=""; card_class="metric-card signal-hold"; emoji="🟡"; adx_label="CHOPPY ⚠️"; lean="No Edge"

col1, col2 = st.columns([2,1])
with col1:
    st.markdown(f"""
    <div class="{card_class}">
      <div class="small">TODAY'S SIGNAL</div>
      <div style="display:flex; align-items:center; gap:12px;">
        <div style="font-size:48px;">{emoji}</div>
        <div style="font-size:42px; font-weight:900;">{signal}</div>
      </div>
      <div class="small">Rule 45/55 • {ts} • Price {price:.4f}</div>
      <div style="display:flex; justify-content:space-between; margin-top:16px;">
        <div>
          <div class="small">PROB UP TOMORROW</div>
          <div class="big">{prob:.1f}%</div>
          <div class="small">{lean}</div>
        </div>
        <div style="text-align:right;">
          <div class="small">ADX</div>
          <div class="big">{adx:.1f}</div>
          <div class="small">{adx_label}</div>
        </div>
      </div>
      <div class="small" style="margin-top:12px;">CHOPPY, HOLD forced (was {was}) | Source: {source} | Was: {was}</div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Prob Gauge — <45% SELL | 45-55% HOLD | >55% BUY")

# --- FAKE BALANCE + STATS ---
# Calculate stats from trades
balance = 100.0
total_pnl = 0.0
wins = 0
losses = 0
closed = 0
profit_factor = 0.0
max_dd = 0.0
streak = 0
longest_win = 0
longest_loss = 0

if len(trades) > 0 and "pnl" in trades.columns:
    pnls = []
    for _, r in trades.iterrows():
        try:
            if str(r.get("status","")).upper() in ["WIN","LOSS","CLOSED","SETTLED"]:
                p = float(r.get("pnl",0) or 0)
                pnls.append(p)
                total_pnl += p
                closed += 1
                if p > 0: wins += 1
                else: losses += 1
        except Exception:
            pass
    balance = 100.0 + total_pnl
    # Profit factor
    gross_profit = sum([p for p in pnls if p>0])
    gross_loss = abs(sum([p for p in pnls if p<0])) or 1
    profit_factor = gross_profit / gross_loss if gross_loss>0 else (gross_profit if gross_profit>0 else 0)
    # Max DD
    equity = [100.0]
    for p in pnls:
        equity.append(equity[-1]+p)
    peak = equity[0]
    dd = 0
    for v in equity:
        if v > peak: peak = v
        d = peak - v
        if d > dd: dd = d
    max_dd = dd
    # Streaks
    cur_streak = 0
    cur_type = None
    for p in pnls:
        if p>0:
            if cur_type=="WIN": cur_streak+=1
            else: cur_streak=1; cur_type="WIN"
            longest_win = max(longest_win, cur_streak)
        else:
            if cur_type=="LOSS": cur_streak+=1
            else: cur_streak=1; cur_type="LOSS"
            longest_loss = max(longest_loss, cur_streak)
    if len(pnls)>0:
        streak = cur_streak
        streak_type = cur_type
    else:
        streak_type="NONE"
else:
    streak_type="NONE"

with col1:
    # Fake Balance Card
    kill_color = "#22c55e" if balance >= 85 else "#eab308" if balance >= 70 else "#ef4444"
    st.markdown(f"""
    <div class="metric-card">
      <div class="small">💰 FAKE BALANCE <span style="float:right; width:12px; height:12px; background:{kill_color}; border-radius:50%; display:inline-block;"></span></div>
      <div class="big">${balance:.2f}</div>
      <div class="small">Start $100 | PnL ${total_pnl:+.2f} | Kill < $70</div>
    </div>
    """, unsafe_allow_html=True)

    # Stats row
    win_rate = (wins/closed*100) if closed>0 else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Win Rate", f"{win_rate:.1f}%", f"{wins}W/{losses}L")
    c2.metric("Profit Factor", f"{profit_factor:.2f}")
    c3.metric("Max DD", f"-${max_dd:.2f}")
    c4.metric("Streak", f"{streak} {streak_type}", f"Best W{longest_win}/L{longest_loss}")

    # Equity Curve
    st.subheader("Equity Curve")
    if len(trades)>0 and "pnl" in trades.columns:
        eq = [100.0]
        for _, r in trades.iterrows():
            try:
                if str(r.get("status","")).upper() in ["WIN","LOSS","CLOSED","SETTLED"]:
                    eq.append(eq[-1]+float(r.get("pnl",0) or 0))
            except Exception:
                pass
        st.line_chart(eq)
    else:
        st.line_chart([100.0])

    # Confidence distribution
    st.subheader("Confidence Distribution")
    if len(trades)>0 and "prob" in trades.columns:
        probs = []
        for _, r in trades.iterrows():
            try:
                p = float(r.get("prob",0))
                if 0<p<=1: p*=100
                probs.append(p)
            except Exception:
                pass
        if len(probs)>0:
            hist = pd.DataFrame({"prob": probs})
            st.bar_chart(hist["prob"].value_counts().sort_index())
        else:
            st.caption("No trades yet")
    else:
        st.caption("No trades yet")

# --- Right column ---
with col2:
    # Live price chart last 24h
    st.subheader("Live EUR/USD — Last 24h (15m)")
    chart_df = get_live_price_chart()
    if len(chart_df)>0:
        st.line_chart(chart_df["Close"])
    else:
        st.caption("Chart unavailable (【entity-Yahoo¦canonical_name=Yahoo】 429?) — using fallback")

    # Live points
    st.subheader("Live Price Points")
    lp_count = len(live_prices) if len(live_prices)>0 else 0
    st.progress(min(lp_count/2880,1.0))
    st.caption(f"{lp_count} / 2880 — 1 point / 15m — 1 month goal")
    if len(live_prices)>0:
        st.dataframe(live_prices.tail(5), use_container_width=True)

    # Signal history sparkline
    st.subheader("Signal History + ADX Trend")
    if len(sig_hist)>0:
        try:
            st.line_chart(sig_hist[["prob_up"]].tail(30) if "prob_up" in sig_hist.columns else sig_hist.tail(30))
        except Exception:
            st.dataframe(sig_hist.tail(10), use_container_width=True)
    else:
        if len(today_sig)>0:
            st.line_chart([prob])
        else:
            st.caption("No history yet — will appear after 2 daily runs")

    # Calendar heatmap
    st.subheader("Calendar Heatmap (PnL per day)")
    if len(trades)>0 and "timestamp" in trades.columns and "pnl" in trades.columns:
        try:
            t = trades.copy()
            t["date"] = pd.to_datetime(t["timestamp"], utc=True).dt.date
            daily = t.groupby("date")["pnl"].sum().reset_index()
            daily["color"] = daily["pnl"].apply(lambda x: "🟩" if x>0 else "🟥" if x<0 else "⬜")
            st.dataframe(daily.tail(14), use_container_width=True)
        except Exception as e:
            st.caption(f"No calendar yet: {e}")
    else:
        st.caption("No trades yet — heatmap will show green/red days")

# --- Paper Trade History with Countdown ---
st.subheader("Paper Trade History")
if len(trades)>0:
    # Add countdown for OPEN trades
    def countdown(ts_str):
        try:
            ts = pd.to_datetime(ts_str, utc=True)
            now = datetime.now(timezone.utc)
            settle = ts + timedelta(hours=20)
            diff = settle - now
            if diff.total_seconds() <=0:
                return "Settling..."
            h = int(diff.total_seconds()//3600)
            m = int((diff.total_seconds()%3600)//60)
            return f"{h}h {m}m"
        except Exception:
            return "-"
    trades_display = trades.copy()
    if "timestamp" in trades_display.columns:
        trades_display["countdown"] = trades_display.apply(lambda r: countdown(r["timestamp"]) if str(r.get("status","")).upper()=="OPEN" else "-", axis=1)
    # Color
    def color_status(val):
        s = str(val).upper()
        if s=="WIN": return "background-color: #dcfce7"
        if s=="LOSS": return "background-color: #fee2e2"
        if s=="OPEN": return "background-color: #fef9c3"
        return ""
    try:
        styled = trades_display.tail(20).style.applymap(color_status, subset=["status"])
        st.dataframe(styled, use_container_width=True)
    except Exception:
        st.dataframe(trades_display.tail(20), use_container_width=True)
else:
    st.caption("No trades yet — will open when prob >55% or <45% and ADX ≥20")

st.caption(f"Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Kill-switch < $70 | Spread 2 pips | Forex-only")
