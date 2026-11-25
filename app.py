# app.py - CANIC FXBOT - FINAL - No tooltips, fixed prob scale 45-55
import os
import pandas as pd
import streamlit as st
from datetime import datetime, timezone, timedelta
import yfinance as yf

st.set_page_config(page_title="CANIC FXBOT", page_icon="📈", layout="wide")

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

col_title, col_toggle = st.columns([3, 1])
with col_title:
    st.markdown("# 📈 CANIC FXBOT")
    st.markdown("**Paper Trading on LIVE Data** • Forex-only • EUR/USD • 1 trade / day • 45/55 Rule • ADX Filter • Auto-refresh 60s 🔄")
with col_toggle:
    st.session_state.dark_mode = st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, key="dm_toggle")

is_dark = st.session_state.dark_mode
bg = "#0f172a" if is_dark else "#f8fafc"
card_bg = "#1e293b" if is_dark else "#ffffff"
text_color = "#f1f5f9" if is_dark else "#0f172a"
sub_text = "#94a3b8" if is_dark else "#64748b"
border = "#334155" if is_dark else "#f1f5f9"

st.markdown(f"""
<style>
.stApp {{ background-color: {bg}; color: {text_color}; }}
header {{visibility: hidden;}}
.block-container {{padding-top: 0.5rem; padding-bottom: 2rem;}}
.card {{ background: {card_bg}; border-radius: 18px; padding: 16px 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); margin-bottom: 14px; border: 1px solid {border}; color: {text_color}; }}
.signal-card {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 50%, #92400e 100%); color: white; border-radius: 22px; padding: 22px; box-shadow: 0 10px 30px rgba(245,158,11,0.35); }}
.balance-card {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white; border-radius: 20px; padding: 20px; }}
.stat-green {{ background: {'#064e3b' if is_dark else '#ecfdf5'}; border-left: 5px solid #10b981; }}
.stat-blue {{ background: {'#1e3a5f' if is_dark else '#eff6ff'}; border-left: 5px solid #3b82f6; }}
.stat-red {{ background: {'#7f1d1d' if is_dark else '#fef2f2'}; border-left: 5px solid #ef4444; }}
.stat-purple {{ background: {'#4c1d95' if is_dark else '#f5f3ff'}; border-left: 5px solid #8b5cf6; }}
.kill-dot {{ width:14px; height:14px; border-radius:50%; display:inline-block; animation: pulse 2s infinite; }}
@keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(34,197,94,0.7); }} 70% {{ box-shadow: 0 0 0 10px rgba(34,197,94,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(34,197,94,0); }} }}
.small-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; opacity: 0.7; font-weight: 700; color: {sub_text}; }}
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

def get_live_chart(live_prices_df):
    try:
        df = yf.download("EURUSD=X", period="1d", interval="15m", auto_adjust=True, progress=False)
        if df is not None and len(df) > 10:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
    except Exception:
        pass
    try:
        if len(live_prices_df) > 0 and "price" in live_prices_df.columns:
            tail = live_prices_df.tail(96).copy()
            tail["timestamp"] = pd.to_datetime(tail["timestamp"], utc=True)
            tail = tail.set_index("timestamp")
            tail = tail.rename(columns={"price": "Close"})
            return tail
    except Exception:
        pass
    return pd.DataFrame()

today_sig = load_csv("results/today_signal.csv")
trades = load_csv("results/paper_trades.csv")
live_prices = load_csv("results/live_prices.csv")
sig_hist = load_csv("results/signal_history.csv")
audit_log = load_csv("results/audit_log.csv")

# =========================
# Prediction Audit Stats
# =========================
pred_accuracy = 0.0
pred_correct = 0
pred_total = 0
latest_audit = None

if len(audit_log) > 0:

    pred_total = len(audit_log)

    if "correct" in audit_log.columns:
        pred_correct = (
            audit_log["correct"]
            .astype(str)
            .str.lower()
            .eq("true")
            .sum()
        )

    if pred_total > 0:
        pred_accuracy = pred_correct / pred_total * 100

    latest_audit = audit_log.iloc[-1]

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

emoji = "🟢" if signal=="BUY" else "🔴" if signal=="SELL" else "🟡"
adx_label = "TRENDING ✅" if adx >= 20 else "CHOPPY ⚠️"
lean = "Lean UP 📈" if prob > 55 else "Lean DOWN 📉" if prob < 45 else "No Edge 😴"

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

st.markdown("---")
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
        <div style="font-size:52px; font-weight:900;">{signal}</div>
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
    </div>
    """, unsafe_allow_html=True)

    if latest_audit is not None:

        audit_result = (
            "✅ CORRECT"
            if str(latest_audit["correct"]).lower() == "true"
            else "❌ WRONG"
        )

        pred_conf = float(
            latest_audit.get("prob_up", 0)
        )

        if 0 < pred_conf <= 1:
            pred_conf *= 100

        entry_price = float(
            latest_audit.get("entry_price", 0)
        )

        st.markdown("##### LAST AUDITED PREDICTION")

        st.markdown(
    f"### {latest_audit['predicted']} → {audit_result}"
)

        st.markdown(
            f"**Actual:** {latest_audit['actual']}"
        )

        st.markdown(
            f"**Confidence:** {pred_conf:.1f}%"
        )

        st.markdown(
            f"**Move:** {latest_audit['move_pct']:+.3f}%"
        )
        
        st.markdown(
            f"**Entry:** {entry_price:.4f}"
        )


s1, s2, s3, s4, s5 = st.columns(5)
with s1:
    st.markdown(f"""<div class="card stat-green"><div class="small-label">Win Rate</div><div style="font-size:32px; font-weight:900;">{win_rate:.1f}%</div><div style="font-size:12px; margin-top:4px;">{wins}W / {losses}L • {closed} closed</div></div>""", unsafe_allow_html=True)
with s2:
    st.markdown(f"""<div class="card stat-blue"><div class="small-label">Profit Factor</div><div style="font-size:32px; font-weight:900;">{profit_factor:.2f}</div></div>""", unsafe_allow_html=True)
with s3:
    st.markdown(f"""<div class="card stat-red"><div class="small-label">Max Drawdown</div><div style="font-size:32px; font-weight:900;">-${max_dd:.2f}</div></div>""", unsafe_allow_html=True)
with s4:
    st.markdown(f"""<div class="card stat-purple"><div class="small-label">Streak</div><div style="font-size:32px; font-weight:900;">{streak} {streak_type}</div><div style="font-size:12px; margin-top:4px;">Best W{longest_win} / L{longest_loss}</div></div>""", unsafe_allow_html=True)
with s5:

    last_result = "—"

    if latest_audit is not None:
        last_result = (
            "✅"
            if str(latest_audit["correct"]).lower() == "true"
            else "❌"
        )

    st.metric(
        label="Prediction Accuracy",
        value=f"{pred_accuracy:.1f}%"
    )

    st.caption(
        f"{pred_correct}/{pred_total} Correct | Last: {last_result}"
    )

e1, e2 = st.columns([1.3, 1])

with e1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 📈 Equity Curve — Zoomed")
    if len(trades)>0 and "pnl" in trades.columns:
        eq = [100.0]
        for _, r in trades.iterrows():
            try:
                if str(r.get("status","")).upper() in ["WIN","LOSS","CLOSED","SETTLED","RESET"]:
                    eq.append(eq[-1]+float(r.get("pnl",0) or 0))
            except Exception:
                pass
        try:
            import altair as alt
            eq_df = pd.DataFrame({"idx": range(len(eq)), "Equity": eq})
            min_e = min(eq) - 1
            max_e = max(eq) + 1
            if min_e == max_e:
                min_e -= 2; max_e += 2
            eq_chart = alt.Chart(eq_df).mark_line(color="#10b981", strokeWidth=3).encode(
                x=alt.X('idx:Q', title='Trades'),
                y=alt.Y('Equity:Q', scale=alt.Scale(domain=[min_e, max_e]), title='Balance $')
            ).properties(height=220)
            st.altair_chart(eq_chart, use_container_width=True)
        except Exception:
            st.line_chart(pd.DataFrame({"Equity": eq}))
    else:
        st.line_chart(pd.DataFrame({"Equity": [100.0]}))
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
                if 0 < p <= 1: p *= 100
                probs.append(p)
            except Exception:
                pass
        if len(probs)>0:
            hist = pd.DataFrame({"prob": probs})
            st.bar_chart(hist["prob"].value_counts().sort_index())
        else:
            st.caption("No trades yet")
    else:
        st.caption("No trades yet — bars will show how many 55%, 60%, 65% trades")
    st.markdown('</div>', unsafe_allow_html=True)

with e2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 💱 Live EUR/USD — Last 24h — ZOOMED to show pips")
    chart_df = get_live_chart(live_prices)
    if len(chart_df)>0 and "Close" in chart_df.columns:
        try:
            import altair as alt
            df_plot = chart_df.reset_index()
            if "timestamp" not in df_plot.columns:
                first_col = df_plot.columns[0]
                df_plot = df_plot.rename(columns={first_col: "timestamp"})
            df_plot = df_plot.tail(96)
            min_p = float(df_plot["Close"].min())
            max_p = float(df_plot["Close"].max())
            if min_p == max_p:
                y_min = min_p - 0.001
                y_max = max_p + 0.001
            else:
                pad = (max_p - min_p) * 0.6
                pad = max(pad, 0.0003)
                y_min = min_p - pad
                y_max = max_p + pad
            chart = alt.Chart(df_plot).mark_line(color="#0ea5e9", strokeWidth=3, point=alt.OverlayMarkDef(color="#0ea5e9", size=30)).encode(
                x=alt.X('timestamp:T', title='Time'),
                y=alt.Y('Close:Q', title='EUR/USD', scale=alt.Scale(domain=[y_min, y_max]))
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
            move_pips = (max_p - min_p) * 10000
            st.caption(f"🔍 Zoomed: {y_min:.5f} - {y_max:.5f} | Move: {move_pips:.1f} pips | {len(df_plot)} points")
            if len(live_prices)>0:
                st.dataframe(live_prices.tail(3), use_container_width=True)
        except Exception as e:
            st.line_chart(chart_df["Close"])
            st.caption(f"Fallback chart: {e}")
    else:
        st.warning("Chart empty — waiting for 2 live points (30m)")
        if len(live_prices)>0:
            st.dataframe(live_prices.tail(5), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 🔮 Signal History + ADX Trend — ZOOMED 45-55")
    if len(sig_hist)>0:
        try:
            import altair as alt
            hist_df = sig_hist.tail(30).copy()
            # Fix prob scale: if stored as 0.477, convert to 47.7
            if "prob_up" in hist_df.columns:
                hist_df["prob_up"] = hist_df["prob_up"].apply(lambda x: x*100 if 0 < x <= 1 else x)
                hist_df = hist_df.reset_index()
                min_h = float(hist_df["prob_up"].min()) - 0.5
                max_h = float(hist_df["prob_up"].max()) + 0.5
                min_h = min(min_h, 45)
                max_h = max(max_h, 55)
                if min_h == max_h:
                    min_h -= 1; max_h += 1
                chart_h = alt.Chart(hist_df).mark_line(color="#8b5cf6", strokeWidth=3, point=alt.OverlayMarkDef(color="#8b5cf6", size=40)).encode(
                    x=alt.X('index:Q', title='Signals'),
                    y=alt.Y('prob_up:Q', title='Prob %', scale=alt.Scale(domain=[min_h, max_h]))
                ).properties(height=200)
                st.altair_chart(chart_h, use_container_width=True)
                st.caption(f"Zoomed {min_h:.1f}% - {max_h:.1f}% | Last {len(hist_df)} signals | 45/55 rule")
            else:
                st.line_chart(hist_df.tail(30))
        except Exception as e:
            st.dataframe(sig_hist.tail(10), use_container_width=True)
            st.caption(f"Fallback: {e}")
    else:
        if len(today_sig)>0:
            st.line_chart(pd.DataFrame({"prob": [prob]}))
            st.caption("1 signal — history builds after 2-3 days")
        else:
            st.caption("No history yet")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 🗓️ Calendar Heatmap (PnL per day)")

    if len(trades)>0 and "timestamp" in trades.columns and "pnl" in trades.columns:
        try:
            t = trades.copy()
            t["date"] = pd.to_datetime(
                t["timestamp"],
                utc=True
            ).dt.date

            daily = (
                t.groupby("date")["pnl"]
                .sum()
                .reset_index()
            )

            st.dataframe(
                daily.tail(10),
                use_container_width=True
            )

        except Exception as e:
            st.caption(
                f"No calendar yet: {e}"
            )

    else:
        st.caption(
            "No trades yet — heatmap will show green/red days"
        )

    st.markdown('</div>', unsafe_allow_html=True)


st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("#### 📋 Paper Trade History")
if len(trades)>0:
    st.dataframe(trades.tail(20), use_container_width=True)
else:
    st.info("No trades yet — will open when prob >55% or <45% and ADX ≥20. Today is HOLD 47.7% so no trade, correct.")
st.markdown('</div>', unsafe_allow_html=True)

st.caption(f"{'🌙 Dark' if is_dark else '☀️ Light'} Mode | Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Kill < $70 | Spread 2 pips | Forex-only | No tooltips")
