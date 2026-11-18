# app.py - CANIC FXBOT - UPGRADE
import os
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timezone, timedelta
import yfinance as yf

st.set_page_config(page_title="CANIC FXBOT", page_icon="📈", layout="wide")

st.markdown("""
<style>
/* Hide Streamlit header */
header {visibility: hidden;}
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
/* Cards */
.card {
  background: white;
  border-radius: 18px;
  padding: 16px 18px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.06);
  margin-bottom: 14px;
  border: 1px solid #f1f5f9;
}
.signal-card {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 50%, #92400e 100%);
  color: white;
  border-radius: 22px;
  padding: 22px;
  box-shadow: 0 10px 30px rgba(245,158,11,0.35);
}
.balance-card {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: white;
  border-radius: 20px;
  padding: 20px;
  box-shadow: 0 8px 24px rgba(15,23,42,0.25);
}
.stat-green { background: linear-gradient(135deg, #ecfdf5, #d1fae5); border-left: 5px solid #10b981; }
.stat-blue { background: linear-gradient(135deg, #eff6ff, #dbeafe); border-left: 5px solid #3b82f6; }
.stat-red { background: linear-gradient(135deg, #fef2f2, #fee2e2); border-left: 5px solid #ef4444; }
.stat-purple { background: linear-gradient(135deg, #f5f3ff, #ede9fe); border-left: 5px solid #8b5cf6; }
.kill-dot { width:14px; height:14px; border-radius:50%; display:inline-block; animation: pulse 2s infinite; }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.7); } 70% { box-shadow: 0 0 0 10px rgba(34,197,94,0); } 100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); } }
.big-num { font-size: 38px; font-weight: 900; line-height: 1; }
.med-num { font-size: 28px; font-weight: 800; }
.small-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; opacity: 0.7; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60*1000, key="refresh")
except Exception:
    pass

os.makedirs("results", exist_ok=True)

def load_csv(path):
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()

def get_live_chart():
    try:
        df = yf.download("EURUSD=X", period="1d", interval="15m", auto_adjust=True, progress=False)
        if df is None or len(df)==0:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return pd.DataFrame()

today_sig = load_csv("results/today_signal.csv")
trades = load_csv("results/paper_trades.csv")
live_prices = load_csv("results/live_prices.csv")
sig_hist = load_csv("results/signal_history.csv")

# Header
st.markdown("# 📈 CANIC FXBOT")
st.markdown("**Paper Trading on LIVE Data** • Forex-only • EUR/USD • 1 trade / day • 45/55 Rule • ADX Filter • Auto-refreshes 60s 🔄")
st.markdown("---")

# Parse signal
if len(today_sig) > 0:
    row = today_sig.iloc[-1]
    prob = float(row.get("prob_up", row.get("prob", 50)))
    if 0 < prob <= 1: prob *= 100
    price = float(row.get("price", 0) or 0)
    adx = float(row.get("adx", 0) or 0)
    signal = str(row.get("signal", "HOLD")).upper()
    source = str(row.get("source", row.get("model", "")))[:18]
    ts = str(row.get("timestamp", row.get("date", "")))
else:
    prob = 0.0; price=0.0; adx=0.0; signal="HOLD"; source=""; ts=""

if signal == "BUY":
    emoji = "🟢"; sig_color = "#10b981"; sig_text = "BUY"
elif signal == "SELL":
    emoji = "🔴"; sig_color = "#ef4444"; sig_text = "SELL"
else:
    emoji = "🟡"; sig_color = "#f59e0b"; sig_text = "HOLD"

adx_label = "TRENDING ✅" if adx >= 20 else "CHOPPY ⚠️"
lean = "Lean UP 📈" if prob > 55 else "Lean DOWN 📉" if prob < 45 else "No Edge 😴"

# Balance stats
balance = 100.0; total_pnl = 0.0; wins = 0; losses = 0; closed = 0; profit_factor = 0.0; max_dd = 0.0; streak = 0; longest_win = 0; longest_loss = 0
if len(trades) > 0 and "pnl" in trades.columns:
    pnls = []
    for _, r in trades.iterrows():
        try:
            if str(r.get("status","")).upper() in ["WIN","LOSS","CLOSED","SETTLED","RESET"]:
                p = float(r.get("pnl",0) or 0)
                pnls.append(p); total_pnl += p; closed += 1
                if p > 0: wins += 1
                elif p < 0: losses += 1
        except Exception:
            pass
    balance = 100.0 + total_pnl
    gross_profit = sum([p for p in pnls if p>0])
    gross_loss = abs(sum([p for p in pnls if p<0])) or 1
    profit_factor = gross_profit / gross_loss if gross_loss>0 else (gross_profit if gross_profit>0 else 0)
    equity = [100.0]
    for p in pnls:
        equity.append(equity[-1]+p)
    peak = equity[0]; dd = 0
    for v in equity:
        if v > peak: peak = v
        d = peak - v
        if d > dd: dd = d
    max_dd = dd
    cur_streak = 0; cur_type = None
    for p in pnls:
        if p>0:
            if cur_type=="WIN": cur_streak+=1
            else: cur_streak=1; cur_type="WIN"
            longest_win = max(longest_win, cur_streak)
        elif p<0:
            if cur_type=="LOSS": cur_streak+=1
            else: cur_streak=1; cur_type="LOSS"
            longest_loss = max(longest_loss, cur_streak)
    if len(pnls)>0:
        streak = cur_streak; streak_type = cur_type
    else:
        streak_type="NONE"
else:
    streak_type="NONE"

win_rate = (wins/closed*100) if closed>0 else 0.0
kill_color = "#22c55e" if balance >= 85 else "#eab308" if balance >= 70 else "#ef4444"

# Layout: Left big signal + Right balance
c1, c2 = st.columns([1.6, 1])

with c1:
    st.markdown(f"""
    <div class="signal-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="font-size:12px; opacity:0.9; font-weight:700; letter-spacing:1px;">TODAY'S SIGNAL • {ts}</div>
        <div style="font-size:12px; background:rgba(255,255,255,0.25); padding:4px 10px; border-radius:20px;">{source}</div>
      </div>
      <div style="display:flex; align-items:center; gap:16px; margin-top:14px;">
        <div style="font-size:56px;">{emoji}</div>
        <div style="font-size:52px; font-weight:900;">{sig_text}</div>
        <div style="margin-left:auto; text-align:right;">
          <div style="font-size:12px; opacity:0.8;">PRICE</div>
          <div style="font-size:22px; font-weight:800;">{price:.4f}</div>
        </div>
      </div>
      <div style="display:flex; justify-content:space-between; margin-top:18px; background:rgba(0,0,0,0.18); border-radius:14px; padding:12px 14px;">
        <div>
          <div style="font-size:10px; opacity:0.8; font-weight:700;">PROB UP TOMORROW</div>
          <div style="font-size:36px; font-weight:900;">{prob:.1f}%</div>
          <div style="font-size:12px; background:white; color:#92400e; padding:2px 8px; border-radius:10px; display:inline-block; font-weight:700;">{lean}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:10px; opacity:0.8; font-weight:700;">ADX</div>
          <div style="font-size:36px; font-weight:900;">{adx:.1f}</div>
          <div style="font-size:12px;">{adx_label}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="balance-card">
      <div style="display:flex; justify-content:space-between;">
        <div style="font-size:11px; opacity:0.7; font-weight:700;">💰 FAKE BALANCE</div>
        <div><span class="kill-dot" style="background:{kill_color};"></span></div>
      </div>
      <div style="font-size:44px; font-weight:900; margin-top:6px;">${balance:.2f}</div>
      <div style="display:flex; gap:8px; margin-top:8px;">
        <div style="background:rgba(255,255,255,0.12); padding:4px 10px; border-radius:10px; font-size:12px;">Start $100</div>
        <div style="background:{'#10b981' if total_pnl>=0 else '#ef4444'}; padding:4px 10px; border-radius:10px; font-size:12px; font-weight:800;">{total_pnl:+.2f}</div>
      </div>
      <div style="margin-top:12px; font-size:11px; opacity:0.6;">Kill &lt; $70 • Spread 2 pips • Equity % sizing • Forex-only</div>
      <div style="margin-top:10px; height:6px; background:rgba(255,255,255,0.15); border-radius:10px;">
        <div style="width:{max(0,min(100, balance))}%; height:6px; background:{kill_color}; border-radius:10px;"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Live Points Card with colour
    lp_count = len(live_prices) if len(live_prices)>0 else 0
    pct = (lp_count/2880*100) if lp_count>0 else 0
    remaining = 2880 - lp_count
    days_left = remaining * 0.25 / 24
    st.markdown(f"""
    <div class="card">
      <div class="small-label">Live Price Points</div>
      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
        <div class="med-num">{lp_count} / 2880</div>
        <div style="background:#f0f9ff; color:#0369a1; padding:4px 10px; border-radius:20px; font-weight:800;">{pct:.2f}%</div>
      </div>
      <div style="height:10px; background:#e2e8f0; border-radius:20px; margin-top:10px;">
        <div style="width:{pct:.2f}%; height:10px; background:linear-gradient(90deg, #0ea5e9, #22d3ee); border-radius:20px;"></div>
      </div>
      <div style="display:flex; justify-content:space-between; margin-top:8px; font-size:12px; opacity:0.7;">
        <span>⏱️ {days_left:.1f} days left</span><span>1 point / 15m</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# Stats 4 cards
s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(f"""<div class="card stat-green"><div class="small-label">Win Rate</div><div class="big-num">{win_rate:.1f}%</div><div style="font-size:12px; margin-top:4px;">{wins}W / {losses}L • {closed} closed</div></div>""", unsafe_allow_html=True)
with s2:
    st.markdown(f"""<div class="card stat-blue"><div class="small-label">Profit Factor</div><div class="big-num">{profit_factor:.2f}</div><div style="font-size:12px; margin-top:4px;">Gross Profit / Gross Loss</div></div>""", unsafe_allow_html=True)
with s3:
    st.markdown(f"""<div class="card stat-red"><div class="small-label">Max Drawdown</div><div class="big-num">-${max_dd:.2f}</div><div style="font-size:12px; margin-top:4px;">Peak to trough</div></div>""", unsafe_allow_html=True)
with s4:
    st.markdown(f"""<div class="card stat-purple"><div class="small-label">Streak</div><div class="big-num">{streak} {streak_type}</div><div style="font-size:12px; margin-top:4px;">Best W{longest_win} / L{longest_loss}</div></div>""", unsafe_allow_html=True)

# Middle row: Equity + Live chart
e1, e2 = st.columns([1.3, 1])

with e1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 📈 Equity Curve")
    if len(trades)>0 and "pnl" in trades.columns:
        eq = [100.0]
        for _, r in trades.iterrows():
            try:
                if str(r.get("status","")).upper() in ["WIN","LOSS","CLOSED","SETTLED","RESET"]:
                    eq.append(eq[-1]+float(r.get("pnl",0) or 0))
            except Exception:
                pass
        st.line_chart(eq, color="#10b981")
    else:
        st.line_chart([100.0], color="#94a3b8")
        st.caption("No trades yet — curve will move after first win/loss")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 🎯 Confidence Distribution")
    if len(trades)>0 and "prob" in trades.columns:
        probs = []
        for _, r in trades.iterrows():
            try:
                if str(r.get("type","")).upper()=="RESET": continue
                p = float(r.get("prob",0))
                if 0<p<=1: p*=100
                probs.append(p)
            except Exception:
                pass
        if len(probs)>0:
            hist = pd.DataFrame({"prob": probs})
            st.bar_chart(hist["prob"].value_counts().sort_index(), color="#f59e0b")
        else:
            st.caption("No trades yet")
    else:
        st.caption("No trades yet — bars will show how many 55%, 60%, 65% trades")
    st.markdown('</div>', unsafe_allow_html=True)

with e2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 💱 Live EUR/USD — Last 24h (15m)")
    chart_df = get_live_chart()
    if len(chart_df)>0:
        st.line_chart(chart_df["Close"], color="#0ea5e9")
        if len(live_prices)>0:
            st.dataframe(live_prices.tail(3), use_container_width=True)
    else:
        st.caption("Chart unavailable (Yahoo 429) — using fallback")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 🔮 Signal History + ADX Trend")
    if len(sig_hist)>0:
        try:
            st.line_chart(sig_hist[["prob_up"]].tail(30) if "prob_up" in sig_hist.columns else sig_hist.tail(30), color="#8b5cf6")
        except Exception:
            st.dataframe(sig_hist.tail(10), use_container_width=True)
    else:
        if len(today_sig)>0:
            st.line_chart([prob], color="#8b5cf6")
            st.caption("1 signal — history builds after 2-3 days")
        else:
            st.caption("No history yet")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 🗓️ Calendar Heatmap (PnL per day)")
    if len(trades)>0 and "timestamp" in trades.columns and "pnl" in trades.columns:
        try:
            t = trades.copy()
            t["date"] = pd.to_datetime(t["timestamp"], utc=True).dt.date
            daily = t.groupby("date")["pnl"].sum().reset_index()
            daily["color"] = daily["pnl"].apply(lambda x: "🟩" if x>0 else "🟥" if x<0 else "⬜")
            st.dataframe(daily.tail(10), use_container_width=True)
        except Exception as e:
            st.caption(f"No calendar yet: {e}")
    else:
        st.caption("No trades yet — heatmap will show green/red days")
    st.markdown('</div>', unsafe_allow_html=True)

# Trade History
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("#### 📋 Paper Trade History")

if len(trades)>0:
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
            return f"{h}h {m}m ⏳"
        except Exception:
            return "-"
    trades_display = trades.copy()
    if "timestamp" in trades_display.columns:
        trades_display["countdown"] = trades_display.apply(lambda r: countdown(r["timestamp"]) if str(r.get("status","")).upper()=="OPEN" else "-", axis=1)
    # Colour
    def color_status(val):
        s = str(val).upper()
        if s=="WIN": return "background-color: #dcfce7; color:#166534; font-weight:700"
        if s=="LOSS": return "background-color: #fee2e2; color:#991b1b; font-weight:700"
        if s=="OPEN": return "background-color: #fef9c3; color:#92400e; font-weight:700"
        if s=="RESET": return "background-color: #dbeafe; color:#1e40af; font-weight:700"
        return ""
    try:
        styled = trades_display.tail(20).style.applymap(color_status, subset=["status"])
        st.dataframe(styled, use_container_width=True)
    except Exception:
        st.dataframe(trades_display.tail(20), use_container_width=True)
else:
    st.info("No trades yet — will open when prob >55% or <45% and ADX ≥20. Today is HOLD 50.7% so no trade, correct.")

st.markdown('</div>', unsafe_allow_html=True)

st.caption(f"Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Kill-switch < $70 | Spread 2 pips | Forex-only | Equity % sizing | Auto-reset 3 days")
