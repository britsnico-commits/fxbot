# app.py - CANIC FXBOT - Fixed Contrast Version
# Light background, dark text OUTSIDE cards, white text INSIDE dark cards only
import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="CANIC FXBOT - Paper Trading", layout="wide", page_icon="📈")

# --- FIXED CSS: DO NOT force all text white ---
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
    /* Outside cards: keep Streamlit default dark text on light bg */
    h1, h2, h3 { color: #0f172a !important; }
    p, span, div, label { color: #0f172a; }
    /* Inside dark cards: force white */
    .big-card, .big-card * { color: #ffffff !important; }
    .big-card {
        border-radius: 16px; padding: 18px 20px; margin-bottom: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.18);
    }
    .card-buy { background: linear-gradient(135deg, #065f46, #10b981); }
    .card-sell { background: linear-gradient(135deg, #7f1d1d, #ef4444); }
    .card-hold { background: linear-gradient(135deg, #92400e, #f59e0b); }
    .card-dark { background: #1e293b; border: 1px solid #334155; }
    .card-green { background: linear-gradient(135deg, #065f46, #059669); }
    .card-red { background: linear-gradient(135deg, #7f1d1d, #dc2626); }
    .card-blue { background: linear-gradient(135deg, #1e40af, #3b82f6); }
    .label { font-size: 12px; opacity: 0.85; text-transform: uppercase; letter-spacing: 1px; }
    .big-num { font-size: 40px; font-weight: 800; line-height: 1.1; margin: 4px 0; }
    .sub { font-size: 14px; opacity: 0.9; }
    .badge {
        display: inline-block; padding: 4px 12px; border-radius: 20px;
        font-size: 13px; font-weight: 700; color: white !important;
    }
    .badge-green { background: #10b981; }
    .badge-orange { background: #f59e0b; }
    .badge-red { background: #ef4444; }
    /* Tables: keep dark text, light bg - readable */
    [data-testid="stDataFrame"] { background: #ffffff; border-radius: 12px; }
    [data-testid="stDataFrame"] * { color: #0f172a !important; }
    /* Section headings: dark, readable */
    .section-title { color: #0f172a !important; font-size: 22px; font-weight: 700; margin: 18px 0 8px 0; }
    .caption-dark { color: #475569 !important; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>📈 CANIC FXBOT <span style='font-size:18px; color:#64748b;'>— Paper Trading on LIVE Data</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#64748b;'>Forex-only • EUR/USD • 1 trade / day • 45/55 Rule • ADX Filter</p>", unsafe_allow_html=True)

def load_csv(path):
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()

def get_balance(trades):
    bal, profit, closed, wins = 100.0, 0.0, 0, 0
    if len(trades) == 0:
        return bal, profit, 0.0, "0/0"
    for _, r in trades.iterrows():
        try:
            pnl = float(r.get("pnl", 0) or 0)
            status = str(r.get("status", "")).upper()
            if status in ["CLOSED", "WIN", "LOSS", "SETTLED"]:
                closed += 1
                profit += pnl
                if pnl > 0: wins += 1
        except Exception:
            pass
    bal = 100.0 + profit
    win_rate = (wins / closed * 100) if closed > 0 else 0.0
    return bal, profit, win_rate, f"{wins}/{closed}" if closed > 0 else f"0/{len(trades)}"

signal_df = load_csv("results/today_signal.csv")
pred_df = load_csv("results/predictions.csv")
trades = load_csv("results/paper_trades.csv")
live = load_csv("results/live_prices.csv")
# Fallback: try other live file names
if len(live) == 0:
    for alt in ["results/live_price_points.csv", "results/live_price.csv", "results/prices.csv"]:
        live = load_csv(alt)
        if len(live) > 0:
            break
acc = load_csv("results/live_accuracy.csv")

# --- FIX: Live points count - use accuracy log if live file empty ---
live_count = len(live)
if live_count == 0 and len(acc) > 0 and "live_points" in acc.columns:
    try:
        live_count = int(acc.iloc[-1]["live_points"])
    except Exception:
        pass

prob, signal, adx, adx_note, source, sig_date, price, raw_signal = 0.0, "HOLD", 0.0, "", "", "", 0.0, ""
if len(signal_df) > 0:
    r = signal_df.iloc[-1]
    try:
        prob = float(r.get("prob_up", r.get("prob", 0)))
        if 0 < prob <= 1.0: prob *= 100
    except Exception: prob = 0.0
    signal = str(r.get("signal", "HOLD"))
    raw_signal = str(r.get("raw_signal", signal))
    try: adx = float(r.get("adx", 0) or 0)
    except Exception: adx = 0.0
    adx_note = str(r.get("adx_note", ""))
    source = str(r.get("source", ""))
    sig_date = str(r.get("date", ""))
    try: price = float(r.get("price", 0) or 0)
    except Exception: price = 0.0
elif len(pred_df) > 0:
    r = pred_df.iloc[-1]
    try:
        raw_p = float(r.get("prob_up", r.get("prob", 0)))
        prob = raw_p * 100 if raw_p <= 1.0 else raw_p
    except Exception: prob = 0.0
    signal = "BUY" if prob > 55 else ("SELL" if prob < 45 else "HOLD")
    raw_signal = signal
    sig_date = str(r.get("date", ""))
    try: price = float(r.get("price", 0) or 0)
    except Exception: price = 0.0
    source = "PREDICTOR_ONLY"

# --- TOP SIGNAL CARD ---
card_class = "card-buy" if signal == "BUY" else ("card-sell" if signal == "SELL" else "card-hold")
emoji = "🟢 BUY" if signal == "BUY" else ("🔴 SELL" if signal == "SELL" else "🟡 HOLD")
adx_badge = "badge-green" if adx >= 20 else "badge-orange"
adx_text = "TRENDING ✅" if adx >= 20 else "CHOPPY ⚠️"

st.markdown(f"""
<div class="big-card {card_class}">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
        <div>
            <div class="label">Today's Signal</div>
            <div class="big-num">{emoji}</div>
            <div class="sub">Rule 45/55 • {sig_date} UTC • Price {price:.4f}</div>
        </div>
        <div style="text-align:right;">
            <div class="label">Prob UP Tomorrow</div>
            <div class="big-num">{prob:.1f}%</div>
            <div class="sub">{"Strong UP" if prob>60 else ("Lean UP" if prob>55 else ("Lean DOWN" if prob<45 else "No Edge"))}</div>
        </div>
        <div style="text-align:right;">
            <div class="label">ADX</div>
            <div class="big-num">{adx:.1f}</div>
            <span class="badge {adx_badge}">{adx_text}</span>
        </div>
    </div>
    <div style="margin-top:12px; font-size:13px; opacity:0.9;">
        {adx_note if adx_note else ''} &nbsp;|&nbsp; Source: {source} &nbsp;|&nbsp; Was: {raw_signal}
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<p style='color:#475569; font-size:13px;'>Prob Gauge — &lt;45% SELL | 45-55% HOLD | &gt;55% BUY</p>", unsafe_allow_html=True)
st.progress(min(max(prob/100, 0), 1.0))

# --- BALANCE ROW ---
balance, profit, win_rate, trades_closed = get_balance(trades)
bal_class = "card-green" if profit > 0 else ("card-red" if profit < 0 else "card-dark")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="big-card {bal_class}"><div class="label">💰 Fake Balance</div><div class="big-num">${balance:.2f}</div><div class="sub">Start $100</div></div>""", unsafe_allow_html=True)
with c2:
    p_class = "card-green" if profit > 0 else ("card-red" if profit < 0 else "card-dark")
    p_emoji = "📈 +" if profit > 0 else ("📉 " if profit < 0 else "➖ ")
    st.markdown(f"""<div class="big-card {p_class}"><div class="label">Fake Profit</div><div class="big-num">{p_emoji}${profit:.2f}</div><div class="sub">{"Winning" if profit>0 else ("Losing" if profit<0 else "Break Even")}</div></div>""", unsafe_allow_html=True)
with c3:
    w_class = "card-green" if win_rate >= 55 else ("card-dark" if win_rate==0 else "card-red")
    st.markdown(f"""<div class="big-card {w_class}"><div class="label">🎯 Win Rate</div><div class="big-num">{win_rate:.1f}%</div><div class="sub">Target &gt;53%</div></div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="big-card card-blue"><div class="label">📊 Trades Closed</div><div class="big-num">{trades_closed}</div><div class="sub">{len(trades)} total • 1/day max</div></div>""", unsafe_allow_html=True)

# --- EQUITY ---
st.markdown("<div class='section-title'>📈 Equity Curve — Are We Winning?</div>", unsafe_allow_html=True)
if len(trades) > 0 and "pnl" in trades.columns:
    equity = [100.0]
    for _, r in trades.iterrows():
        try:
            if str(r.get("status","")).upper() in ["CLOSED","WIN","LOSS","SETTLED"]:
                equity.append(equity[-1] + float(r.get("pnl",0) or 0))
        except Exception: pass
    if len(equity)==1: equity=[100.0,100.0]
    st.line_chart(pd.DataFrame({"Balance": equity}), height=220)
else:
    st.line_chart(pd.DataFrame({"Balance": [100.0,100.0]}), height=220)
st.markdown("<p class='caption-dark'>Start $100 fake. If line goes up over 1 month, daily model works.</p>", unsafe_allow_html=True)

# --- TRADES ---
st.markdown("<div class='section-title'>📋 Paper Trade History</div>", unsafe_allow_html=True)
if len(trades) > 0:
    show = trades.copy()
    cols = [c for c in ["timestamp","signal","prob","price","stake","type","pnl","status"] if c in show.columns]
    st.dataframe(show[cols] if cols else show, use_container_width=True)
else:
    st.markdown("<div class='big-card card-dark'>No trades yet. Bot opens 1 trade/day when Prob &gt;55% or &lt;45% and ADX ≥20.</div>", unsafe_allow_html=True)

# --- LIVE POINTS - FIXED COUNT ---
pct = live_count/2880*100 if live_count>0 else 0
st.markdown(f"<div class='section-title'>🔴 Live Price Points: {live_count} / 2880 ({pct:.1f}% of 1 month)</div>", unsafe_allow_html=True)
st.progress(min(live_count/2880, 1.0))
if len(live) > 0:
    show_live = live.tail(10).copy()
    cols_live = [c for c in ["timestamp","price"] if c in show_live.columns]
    st.dataframe(show_live[cols_live] if cols_live else show_live, use_container_width=True)
elif live_count > 0:
    st.markdown(f"<p class='caption-dark'>Collecting live points — {live_count} points logged (from accuracy log). Live price table file not found, but count is correct.</p>", unsafe_allow_html=True)
else:
    st.write("No live points yet.")

# --- ACCURACY ---
st.markdown("<div class='section-title'>🧪 Live Accuracy Log</div>", unsafe_allow_html=True)
if len(acc) > 0:
    st.dataframe(acc, use_container_width=True)
else:
    st.write("No accuracy log yet.")

st.divider()
st.markdown("<p class='caption-dark'>CANIC FXBOT | Forex-only | EUR/USD | 1 trade/day max | $10-$20 stake | Kill-switch if balance &lt; $70 | No trade weekends / NFP Friday | ADX &lt;20 = HOLD</p>", unsafe_allow_html=True)
