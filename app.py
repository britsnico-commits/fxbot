# app.py - CANIC FXBOT - With Kill-Switch Light + Signal History + ADX Trend + Countdown
import os
import pandas as pd
import streamlit as st
import altair as alt
from datetime import datetime, timezone

st.set_page_config(page_title="CANIC FXBOT - Paper Trading", layout="wide", page_icon="📈")
st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)

st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
    h1, h2, h3 { color: #0f172a !important; }
    p, span, div, label { color: #0f172a; }
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
    .card-purple { background: linear-gradient(135deg, #5b21b6, #8b5cf6); }
    .card-yellow { background: linear-gradient(135deg, #92400e, #f59e0b); }
    .label { font-size: 12px; opacity: 0.85; text-transform: uppercase; letter-spacing: 1px; }
    .big-num { font-size: 40px; font-weight: 800; line-height: 1.1; margin: 4px 0; }
    .sub { font-size: 14px; opacity: 0.9; }
    .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 700; color: white !important; }
    .badge-green { background: #10b981; }
    .badge-orange { background: #f59e0b; }
    .badge-red { background: #ef4444; }
    [data-testid="stDataFrame"] { background: #ffffff; border-radius: 12px; }
    [data-testid="stDataFrame"] * { color: #0f172a !important; }
    .section-title { color: #0f172a !important; font-size: 22px; font-weight: 700; margin: 18px 0 8px 0; }
    .caption-dark { color: #475569 !important; font-size: 13px; }
    .live-price { color: #0f172a !important; font-size: 20px; font-weight: 700; margin: 6px 0; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>📈 CANIC FXBOT <span style='font-size:18px; color:#64748b;'>— Paper Trading on LIVE Data</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#64748b;'>Forex-only • EUR/USD • 1 trade / day • 45/55 Rule • ADX Filter • Auto-refreshes every 60s 🔄</p>", unsafe_allow_html=True)

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

def parse_ts(s):
    try:
        return pd.to_datetime(str(s), utc=True)
    except Exception:
        return None

signal_df = load_csv("results/today_signal.csv")
pred_df = load_csv("results/predictions.csv")
trades = load_csv("results/paper_trades.csv")
live = load_csv("results/live_prices.csv")
if len(live) == 0:
    for alt_path in ["results/live_price_points.csv", "results/live_price.csv", "results/prices.csv"]:
        live = load_csv(alt_path)
        if len(live) > 0:
            break
acc = load_csv("results/live_accuracy.csv")
hist = load_csv("results/signal_history.csv")

live_count = len(live)
if live_count == 0 and len(acc) > 0 and "live_points" in acc.columns:
    try: live_count = int(acc.iloc[-1]["live_points"])
    except Exception: pass
if len(acc) > 0 and "live_points" in acc.columns:
    try:
        acc_max = int(acc["live_points"].max())
        if acc_max > live_count: live_count = acc_max
    except Exception: pass

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

card_class = "card-buy" if signal == "BUY" else ("card-sell" if signal == "SELL" else "card-hold")
emoji = "🟢 BUY" if signal == "BUY" else ("🔴 SELL" if signal == "SELL" else "🟡 HOLD")
adx_badge = "badge-green" if adx >= 20 else "badge-orange"
adx_text = "TRENDING ✅" if adx >= 20 else "CHOPPY ⚠️"

st.markdown(f"""
<div class="big-card {card_class}">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
        <div><div class="label">Today's Signal</div><div class="big-num">{emoji}</div><div class="sub">Rule 45/55 • {sig_date} UTC • Price {price:.4f}</div></div>
        <div style="text-align:right;"><div class="label">Prob UP Tomorrow</div><div class="big-num">{prob:.1f}%</div><div class="sub">{"Strong UP" if prob>60 else ("Lean UP" if prob>55 else ("Lean DOWN" if prob<45 else "No Edge"))}</div></div>
        <div style="text-align:right;"><div class="label">ADX</div><div class="big-num">{adx:.1f}</div><span class="badge {adx_badge}">{adx_text}</span></div>
    </div>
    <div style="margin-top:12px; font-size:13px; opacity:0.9;">{adx_note if adx_note else ''} &nbsp;|&nbsp; Source: {source} &nbsp;|&nbsp; Was: {raw_signal}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<p style='color:#475569; font-size:13px;'>Prob Gauge — &lt;45% SELL | 45-55% HOLD | &gt;55% BUY</p>", unsafe_allow_html=True)
st.progress(min(max(prob/100, 0), 1.0))

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

# --- NEW: KILL-SWITCH LIGHT ---
# Rules: Start $100, Kill-switch at $70 (stop trading), Warning at $85
KILL = 70.0
WARN = 85.0
buffer_amt = balance - KILL
if balance < KILL:
    ks_class = "card-red"
    ks_emoji = "🔴 STOPPED"
    ks_text = f"Balance ${balance:.2f} is BELOW kill-switch ${KILL:.0f} — Bot has STOPPED trading. Reset needed."
    ks_sub = "No new trades will open until you reset."
elif balance < WARN:
    ks_class = "card-yellow"
    ks_emoji = "🟡 WARNING"
    ks_text = f"Balance ${balance:.2f} — Only ${buffer_amt:.2f} buffer left before kill-switch at ${KILL:.0f}"
    ks_sub = f"1 more loss (${10:.0f}) = ${balance-10:.2f}. 2 more losses = STOP. Trade carefully."
else:
    ks_class = "card-green"
    ks_emoji = "🟢 SAFE"
    ks_text = f"Balance ${balance:.2f} — ${buffer_amt:.2f} buffer above kill-switch at ${KILL:.0f}"
    ks_sub = f"Can survive {int(buffer_amt // 10)} more $10 losses before stopping. Safe to trade."

# Progress: 0% = $70 (dead), 100% = $120 (great) - clamp
ks_pct = max(0.0, min(1.0, (balance - KILL) / (120 - KILL)))
st.markdown(f"<div class='section-title'>🛡️ Kill-Switch — How Safe Are We?</div>", unsafe_allow_html=True)
st.markdown(f"""
<div class="big-card {ks_class}">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
        <div><div class="label">Kill-Switch Status</div><div class="big-num">{ks_emoji}</div><div class="sub">{ks_text}</div></div>
        <div style="text-align:right;"><div class="label">Buffer Left</div><div class="big-num">${buffer_amt:.2f}</div><div class="sub">Kill at $70 • Start $100</div></div>
    </div>
    <div style="margin-top:10px; font-size:13px; opacity:0.9;">{ks_sub}</div>
</div>
""", unsafe_allow_html=True)
st.markdown("<p style='color:#475569; font-size:13px;'>Kill-Switch Gauge — Red zone = $70 STOP &nbsp;|&nbsp; Yellow = $70-$85 WARNING &nbsp;|&nbsp; Green = $85+ SAFE</p>", unsafe_allow_html=True)
st.progress(ks_pct)

# --- OPEN TRADE COUNTDOWN ---
open_trade = None
if len(trades) > 0 and "status" in trades.columns:
    opens = trades[trades["status"].astype(str).str.upper() == "OPEN"]
    if len(opens) > 0:
        open_trade = opens.iloc[-1]
if open_trade is not None:
    try:
        o_sig = str(open_trade.get("signal", "BUY"))
        o_price = float(open_trade.get("price", 0) or 0)
        o_prob = float(open_trade.get("prob", 0) or 0)
        o_stake = float(open_trade.get("stake", 10) or 10)
        o_ts = parse_ts(open_trade.get("timestamp", ""))
        now_utc = pd.Timestamp.now(tz="UTC")
        if o_ts is not None:
            settle = o_ts + pd.Timedelta(hours=20)
            remaining = settle - now_utc
            total_sec = int(remaining.total_seconds())
            if total_sec < 0:
                countdown_txt = "⏰ Settling now — check next Daily Run"
                need_txt = "Settling"
            else:
                h = total_sec // 3600; m = (total_sec % 3600) // 60
                countdown_txt = f"⏳ Settles in {h}h {m}m — at {settle.strftime('%H:%M')} UTC"
                if o_sig == "BUY":
                    need_txt = f"Needs EUR/USD &gt; {o_price:.4f} to WIN (+${o_stake*0.85:.2f}) • Below = LOSS (-${o_stake:.0f})"
                else:
                    need_txt = f"Needs EUR/USD &lt; {o_price:.4f} to WIN (+${o_stake*0.85:.2f}) • Above = LOSS (-${o_stake:.0f})"
            st.markdown(f"<div class='section-title'>⏱️ Open Trade — Countdown</div>", unsafe_allow_html=True)
            st.markdown(f"""<div class="big-card card-purple"><div class="label">Open Trade</div><div class="big-num">{o_sig} {o_prob:.1f}% @ {o_price:.4f} • ${o_stake:.0f} stake</div><div class="sub">{countdown_txt}</div><div class="sub" style="margin-top:6px;">{need_txt}</div></div>""", unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"<p class='caption-dark'>Open trade countdown failed: {e}</p>", unsafe_allow_html=True)
else:
    st.markdown("<p class='caption-dark'>No open trade — next trade opens when Prob &gt;55% or &lt;45% and ADX ≥20.</p>", unsafe_allow_html=True)

# --- SIGNAL HISTORY + ADX TREND ---
st.markdown("<div class='section-title'>📊 Signal History — Is Confidence Rising or Falling?</div>", unsafe_allow_html=True)
if len(hist) > 0:
    hist_show = hist.tail(14).copy()
    prob_df = pd.DataFrame({"Prob": hist_show["prob_up"].values})
    base = alt.Chart(prob_df.reset_index()).mark_line(color="#2563eb", strokeWidth=3, point=True).encode(x=alt.X("index", title="Day (old → new)"), y=alt.Y("Prob", scale=alt.Scale(domain=[35, 65]))).properties(height=200)
    rule = alt.Chart(pd.DataFrame({"y": [55, 45]})).mark_rule(color="#f59e0b", strokeDash=[4,4]).encode(y="y")
    st.altair_chart(base + rule, use_container_width=True)
    try:
        probs = hist_show["prob_up"].values
        first_p = float(probs[0]); last_p = float(probs[-1])
        trend = "📈 Rising" if last_p > first_p else ("📉 Falling" if last_p < first_p else "➖ Flat")
        st.markdown(f"<p class='caption-dark'>Last {len(probs)} days: {first_p:.1f}% → {last_p:.1f}% — {trend} &nbsp;|&nbsp; Orange lines = 45% / 55% thresholds.</p>", unsafe_allow_html=True)
        st.dataframe(hist_show[["date","prob_up","signal","adx","price"]], use_container_width=True)
    except Exception:
        pass
else:
    st.markdown("<p class='caption-dark'>History starts building from today. Run Daily Run tomorrow and you’ll see 2 points. Today: Prob {:.1f}% ADX {:.1f}</p>".format(prob, adx), unsafe_allow_html=True)
    if prob > 0:
        st.altair_chart(alt.Chart(pd.DataFrame({"Prob": [prob]})).mark_point(color="#2563eb", size=100).encode(y=alt.Y("Prob", scale=alt.Scale(domain=[35,65]))).properties(height=150), use_container_width=True)

st.markdown("<div class='section-title'>🌊 ADX Trend — Is a Trend Building?</div>", unsafe_allow_html=True)
if len(hist) > 0 and "adx" in hist.columns:
    hist_adx = hist.tail(14).copy()
    adx_df = pd.DataFrame({"ADX": hist_adx["adx"].values})
    adx_chart = alt.Chart(adx_df.reset_index()).mark_line(color="#059669", strokeWidth=3, point=True).encode(x=alt.X("index", title="Day (old → new)"), y=alt.Y("ADX", scale=alt.Scale(domain=[0, 35]))).properties(height=200)
    adx_line = alt.Chart(pd.DataFrame({"y": [20]})).mark_rule(color="#ef4444", strokeDash=[4,4]).encode(y="y")
    st.altair_chart(adx_chart + adx_line, use_container_width=True)
    try:
        adxs = hist_adx["adx"].values
        first_a = float(adxs[0]); last_a = float(adxs[-1])
        a_trend = "📈 Building toward trend" if last_a > first_a else ("📉 Getting choppier" if last_a < first_a else "➖ Flat")
        st.markdown(f"<p class='caption-dark'>Last {len(adxs)} days: ADX {first_a:.1f} → {last_a:.1f} — {a_trend} &nbsp;|&nbsp; Red line = 20. Above = trade allowed.</p>", unsafe_allow_html=True)
    except Exception:
        pass
else:
    st.markdown(f"<p class='caption-dark'>ADX history starts today: ADX {adx:.1f}. Tomorrow you’ll see if it’s climbing toward 20.</p>", unsafe_allow_html=True)

# --- LIVE EUR/USD CHART ---
st.markdown("<div class='section-title'>💹 Live EUR/USD — What Is It Doing Right Now?</div>", unsafe_allow_html=True)
live_chart_ok = False
try:
    import yfinance as yf
    df_live = yf.download("EURUSD=X", period="1d", interval="15m", auto_adjust=True, progress=False)
    if df_live is not None and len(df_live) > 0:
        if isinstance(df_live.columns, pd.MultiIndex):
            df_live.columns = df_live.columns.get_level_values(0)
        close = df_live["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        last = float(close.iloc[-1]); first = float(close.iloc[0])
        chg = last - first; chg_pct = chg / first * 100 if first != 0 else 0
        chg_emoji = "🟢" if chg >= 0 else "🔴"; chg_word = "UP" if chg >= 0 else "DOWN"
        st.markdown(f"<p class='live-price'>EUR/USD Now: {last:.4f} &nbsp; {chg_emoji} {chg:+.4f} ({chg_pct:+.2f}% today) — {chg_word}</p>", unsafe_allow_html=True)
        chart_df = pd.DataFrame({"EUR/USD": close.values})
        ymin = float(chart_df["EUR/USD"].min()) - 0.0005; ymax = float(chart_df["EUR/USD"].max()) + 0.0005
        chart = alt.Chart(chart_df.reset_index()).mark_line(color="#2563eb", strokeWidth=2).encode(x=alt.X("index", title="15-min bars"), y=alt.Y("EUR/USD", scale=alt.Scale(domain=[ymin, ymax]))).properties(height=280)
        st.altair_chart(chart, use_container_width=True)
        st.markdown("<p class='caption-dark'>Last 24h, 15-min prices. Zoomed to show real moves. Auto-refreshes every 60s.</p>", unsafe_allow_html=True)
        live_chart_ok = True
except Exception:
    live_chart_ok = False
if not live_chart_ok:
    if len(live) > 0 and "price" in live.columns:
        chart_df2 = pd.DataFrame({"EUR/USD": live["price"].values})
        ymin2 = float(chart_df2["EUR/USD"].min()) - 0.0005; ymax2 = float(chart_df2["EUR/USD"].max()) + 0.0005
        chart2 = alt.Chart(chart_df2.reset_index()).mark_line(color="#2563eb", strokeWidth=2).encode(x=alt.X("index", title="Bot points"), y=alt.Y("EUR/USD", scale=alt.Scale(domain=[ymin2, ymax2]))).properties(height=280)
        st.altair_chart(chart2, use_container_width=True)
        st.markdown(f"<p class='caption-dark'>From your bot — {len(live)} points collected.</p>", unsafe_allow_html=True)
    else:
        st.write("No live chart data yet — run Daily Run once.")

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
    eq_df = pd.DataFrame({"Balance": equity})
    eq_chart = alt.Chart(eq_df.reset_index()).mark_line(color="#059669", strokeWidth=3).encode(x=alt.X("index", title="Closed trades"), y=alt.Y("Balance", scale=alt.Scale(domain=[90, 120]))).properties(height=220)
    st.altair_chart(eq_chart, use_container_width=True)
else:
    eq_df = pd.DataFrame({"Balance": [100.0, 100.0]})
    eq_chart = alt.Chart(eq_df.reset_index()).mark_line(color="#059669", strokeWidth=3).encode(x=alt.X("index", title="Closed trades"), y=alt.Y("Balance", scale=alt.Scale(domain=[90, 120]))).properties(height=220)
    st.altair_chart(eq_chart, use_container_width=True)
st.markdown("<p class='caption-dark'>Start $100 fake. Zoomed 90-120 so small wins/losses are visible.</p>", unsafe_allow_html=True)

# --- TRADES COLOURED ---
st.markdown("<div class='section-title'>📋 Paper Trade History</div>", unsafe_allow_html=True)
if len(trades) > 0:
    show = trades.copy()
    cols = [c for c in ["timestamp","signal","prob","price","stake","type","pnl","status"] if c in show.columns]
    show = show[cols] if cols else show
    def color_row(row):
        try:
            status = str(row.get("status","")).upper()
            pnl = float(row.get("pnl", 0) or 0)
            if status == "OPEN":
                return ["background-color: #fef9c3; color: #854d0e; font-weight: 600"] * len(row)
            elif pnl > 0 or status == "WIN":
                return ["background-color: #dcfce7; color: #166534; font-weight: 600"] * len(row)
            elif pnl < 0 or status == "LOSS":
                return ["background-color: #fee2e2; color: #991b1b; font-weight: 600"] * len(row)
            else:
                return [""] * len(row)
        except Exception:
            return [""] * len(row)
    try:
        styled = show.style.apply(color_row, axis=1)
        st.dataframe(styled, use_container_width=True)
    except Exception:
        st.dataframe(show, use_container_width=True)
    st.markdown("<p class='caption-dark'>🟡 Yellow = OPEN &nbsp;|&nbsp; 🟢 Green = WIN &nbsp;|&nbsp; 🔴 Red = LOSS</p>", unsafe_allow_html=True)
else:
    st.markdown("<div class='big-card card-dark'>No trades yet. Bot opens 1 trade/day when Prob &gt;55% or &lt;45% and ADX ≥20.</div>", unsafe_allow_html=True)

pct = live_count/2880*100 if live_count>0 else 0
st.markdown(f"<div class='section-title'>🔴 Live Price Points: {live_count} / 2880 ({pct:.1f}% of 1 month)</div>", unsafe_allow_html=True)
st.progress(min(live_count/2880, 1.0))
if len(live) > 0:
    show_live = live.tail(10).copy()
    cols_live = [c for c in ["timestamp","price"] if c in show_live.columns]
    st.dataframe(show_live[cols_live] if cols_live else show_live, use_container_width=True)
elif live_count > 0:
    st.markdown(f"<p class='caption-dark'>Collecting live points — {live_count} points logged (from accuracy log).</p>", unsafe_allow_html=True)
else:
    st.write("No live points yet.")

st.markdown("<div class='section-title'>🧪 Live Accuracy Log</div>", unsafe_allow_html=True)
if len(acc) > 0:
    st.dataframe(acc, use_container_width=True)
else:
    st.write("No accuracy log yet.")

st.divider()
st.markdown("<p class='caption-dark'>CANIC FXBOT | Forex-only | EUR/USD | 1 trade/day max | $10-$20 stake | Kill-switch if balance &lt; $70 | No trade weekends / NFP Friday | ADX &lt;20 = HOLD • Auto-refresh 60s</p>", unsafe_allow_html=True)
