
import pandas as pd
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path("results")
PRED = RESULTS / "predictions.csv"

def create_dashboard():
    if not PRED.exists():
        print("No predictions.csv")
        return
    
    df = pd.read_csv(PRED)
    # find cols
    ret_col = [c for c in df.columns if "actual" in c.lower() and "return" in c.lower()][0]
    ens_col = [c for c in df.columns if "ensemble" in c.lower()][0]
    date_col = df.columns[0]
    df["Date"] = pd.to_datetime(df[date_col])
    df = df.sort_values("Date")
    
    # create figure with 3 panels
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    
    # 1. Price proxy (cumulative actual returns)
    df["price_proxy"] = (1 + df[ret_col]).cumprod()
    ax1.plot(df["Date"], df["price_proxy"], label="EUR/USD proxy", color="gray", alpha=0.7)
    ax1.set_ylabel("Price proxy")
    ax1.set_title("EUR/USD with Buy/Sell signals (Ensemble >0.55 BUY, <0.45 SELL)")
    ax1.grid(True, alpha=0.3)
    
    # buy/sell markers
    buys = df[df[ens_col] > 0.55]
    sells = df[df[ens_col] < 0.45]
    ax1.scatter(buys["Date"], buys["price_proxy"], color="green", marker="^", s=30, label="BUY signal", alpha=0.7)
    ax1.scatter(sells["Date"], sells["price_proxy"], color="red", marker="v", s=30, label="SELL signal", alpha=0.7)
    ax1.legend()
    
    # 2. Probability
    ax2.plot(df["Date"], df[ens_col], color="blue", label="Ensemble prob UP")
    ax2.axhline(0.55, color="green", linestyle="--", label="BUY threshold 0.55")
    ax2.axhline(0.45, color="red", linestyle="--", label="SELL threshold 0.45")
    ax2.axhline(0.5, color="black", linestyle="-", alpha=0.3)
    ax2.set_ylabel("Prob UP tomorrow")
    ax2.set_ylim(0.2, 0.8)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Cumulative return (from equity_curve logic)
    # simple equity for ensemble always trade
    COST = 0.00009
    df["signal"] = df[ens_col].apply(lambda x: 1 if x>0.5 else -1)
    df["pos_change"] = df["signal"].diff().abs().fillna(0)
    df["pnl"] = df["signal"].shift(1) * df[ret_col] - df["pos_change"]*COST
    df["cum_ret"] = (1 + df["pnl"]).cumprod() - 1
    ax3.plot(df["Date"], df["cum_ret"], color="blue", label="Ensemble Always Trade")
    ax3.set_ylabel("Cumulative return")
    ax3.set_xlabel("Date")
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(RESULTS / "live_dashboard.png", dpi=150)
    print(f"Saved {RESULTS / 'live_dashboard.png'}")
    plt.close()

if __name__ == "__main__":
    create_dashboard()

