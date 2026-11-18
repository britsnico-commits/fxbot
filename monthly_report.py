import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

Path("results").mkdir(exist_ok=True)

# Load trades
p = Path("results/paper_trades.csv")
trades = pd.DataFrame()
if p.exists():
    try:
        trades = pd.read_csv(p)
    except:
        pass

# Load live log
live_count = 0
if Path("results/live_log.csv").exists():
    try:
        live_count = len(pd.read_csv("results/live_log.csv"))
    except:
        pass

# Load model compare
compare_text = ""
if Path("results/model_compare.csv").exists():
    try:
        comp = pd.read_csv("results/model_compare.csv")
        # Last row per model
        last = comp.groupby("model").tail(1)
        compare_text = last.to_string(index=False)
    except:
        pass

# Calculate stats
total_trades = len(trades)
closed = trades[trades['status'].astype(str).str.contains('CLOSED')] if len(trades)>0 and 'status' in trades.columns else pd.DataFrame()
total_pnl = float(closed['pnl'].sum()) if len(closed)>0 and 'pnl' in closed.columns else 0
win_rate = float((closed['pnl']>0).mean()*100) if len(closed)>0 else 0
balance = 100 + total_pnl
best = float(closed['pnl'].max()) if len(closed)>0 else 0
worst = float(closed['pnl'].min()) if len(closed)>0 else 0

# --- Equity chart ---
equity = [100]
for pnl in closed['pnl'].tolist() if len(closed)>0 else []:
    equity.append(equity[-1] + pnl)

plt.figure(figsize=(8,3))
plt.plot(equity, marker='o', linewidth=2)
plt.axhline(100, color='gray', linestyle='--', alpha=0.5)
plt.title(f"CANIC FXBOT Equity Curve - Balance ${balance:.2f}")
plt.ylabel("Fake Balance ($)")
plt.xlabel("Closed Trades")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("results/equity_chart.png", dpi=150)
plt.close()
print(f"Chart saved, balance ${balance:.2f}")

# --- PDF ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    now = datetime.now(timezone.utc)
    pdf_path = f"results/CANIC_Monthly_Report_{now.strftime('%Y-%m')}.pdf"
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4
    y = h - 40
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, y, "CANIC FXBOT - Monthly Report")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Period: {now.strftime('%B %Y')}  |  Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    y -= 25
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "Summary")
    y -= 18
    c.setFont("Helvetica", 11)
    lines = [
        f"Live Points Collected: {live_count} / 2880",
        f"Total Trades: {total_trades} (Closed: {len(closed)})",
        f"Win Rate: {win_rate:.1f}%",
        f"Total Fake PnL: ${total_pnl:.2f}",
        f"Fake Balance: ${balance:.2f} (Start $100)",
        f"Best Trade: ${best:.2f}  |  Worst Trade: ${worst:.2f}",
        f"Rule: 45/55 Threshold | Stake: $10-$20 Position Sizing",
        f"Filters: ADX >20, Weekend, NFP Friday, Kill-switch $70",
    ]
    for line in lines:
        c.drawString(40, y, line)
        y -= 16
    y -= 10
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "Equity Curve")
    y -= 10
    # Image
    try:
        c.drawImage("results/equity_chart.png", 40, y-180, width=500, height=180)
        y -= 200
    except Exception as e:
        print(f"Chart embed failed: {e}")
        y -= 20
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "Model Comparison (Latest)")
    y -= 16
    c.setFont("Helvetica", 9)
    for line in compare_text.split("\n")[:10]:
        c.drawString(40, y, line[:100])
        y -= 12
    y -= 10
    c.setFont("Helvetica", 10)
    c.drawString(40, y, "Decision Rule: Win >53% = Keep Daily | Win <53% = Build Intraday")
    y -= 16
    c.drawString(40, y, "Dashboard: https://canictrade.streamlit.app")
    c.save()
    print(f"PDF saved: {pdf_path}")
except Exception as e:
    print(f"PDF failed: {e}")
    # Fallback txt
    Path("results/monthly_summary.txt").write_text(f"Balance ${balance:.2f} Win {win_rate:.1f}% Trades {total_trades} PnL ${total_pnl:.2f} Live {live_count}")

print("monthly_report done")
