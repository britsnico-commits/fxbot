"""
FXBOT Live Trading Bot - Deriv (Free, Works in SA, No PC Needed, No $5 VPS)
Uses Deriv API - free demo, works in South Africa, runs on GitHub Actions free

Why Deriv for SA free live trading:
- Works in South Africa (OANDA blocked, MT5 needs Windows + $5 VPS)
- Free demo $10k virtual money
- Pure Python API - no MT5 terminal needed
- Can run on GitHub Actions every 15 mins (public repo = unlimited free) OR Render free
- No PC on, no $5/month

Paper-trade only, not financial advice.
Model: Logistic +9.8% PASS vs BH 6.2% - 78 vars btc_ret_1 top

Setup:
1. Go to https://deriv.com -> Sign up -> Demo account $10k virtual
2. Go to https://app.deriv.com/account/api-token -> Create token -> Copy
3. Set env var DERIV_API_TOKEN
4. pip install websocket-client pandas
5. python live_bot_deriv.py --dry-run --once
6. python live_bot_deriv.py --live --once
7. For 24/7 free: push to GitHub, enable GitHub Actions (already have every 15 mins workflow)

Runs: Checks today_signal.txt SELL 40.6% and places EUR/USD Rise/Fall contract on Deriv demo.
"""

import os
import argparse
import time
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    import websocket
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
APP_ID = "1089"  # Public demo app_id
INSTRUMENT = "frxEURUSD"  # Deriv symbol for EUR/USD
UNITS = 10  # $10 stake

def get_today_signal():
    p = Path("today_signal.txt")
    if not p.exists():
        return {"signal": "SELL", "prob_up": 0.406}
    txt = p.read_text().upper()
    signal = "SELL" if "SELL" in txt else "BUY" if "BUY" in txt else "HOLD"
    prob = 0.406
    try:
        import re
        m = re.search(r"PROB UP[^0-9]*([0-9.]+)", txt)
        if m:
            v = float(m.group(1))
            prob = v/100 if v>1 else v
    except:
        pass
    return {"signal": signal, "prob_up": prob, "raw": txt}

def place_deriv_order(signal, dry_run=True):
    if signal == "HOLD":
        print("[HOLD] No trade - low confidence 0.45-0.55")
        return True

    # Deriv contract: CALL = BUY (up), PUT = SELL (down)
    contract_type = "CALL" if signal == "BUY" else "PUT"
    
    if dry_run:
        print(f"[DRY-RUN] Would place Deriv {contract_type} {INSTRUMENT} ${UNITS} stake - Signal {signal} Prob {get_today_signal()['prob_up']:.3f}")
        print(f"  -> This would be a Rise/Fall contract if live")
        return True

    if not DERIV_API_TOKEN:
        print("[ERROR] Set DERIV_API_TOKEN env var")
        print("Get token at https://app.deriv.com/account/api-token")
        return False

    if not WS_AVAILABLE:
        print("[ERROR] pip install websocket-client")
        return False

    try:
        # Connect to Deriv
        ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
        ws = websocket.create_connection(ws_url)
        
        # Authorize
        ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))
        auth_resp = json.loads(ws.recv())
        if "error" in auth_resp:
            print(f"[ERROR] Deriv auth failed: {auth_resp['error']}")
            ws.close()
            return False
        
        print(f"[DERIV] Authorized - Balance: {auth_resp.get('authorize', {}).get('balance', 'unknown')}")

        # Proposal
        proposal = {
            "proposal": 1,
            "amount": UNITS,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "duration": 1,
            "duration_unit": "d",
            "symbol": INSTRUMENT
        }
        ws.send(json.dumps(proposal))
        prop_resp = json.loads(ws.recv())
        
        if "error" in prop_resp:
            print(f"[ERROR] Proposal failed: {prop_resp['error']}")
            ws.close()
            return False

        proposal_id = prop_resp["proposal"]["id"]
        print(f"[DERIV] Proposal {proposal_id} - Ask price: ${prop_resp['proposal']['ask_price']}")

        # Buy
        ws.send(json.dumps({"buy": proposal_id, "price": UNITS}))
        buy_resp = json.loads(ws.recv())
        
        if "error" in buy_resp:
            print(f"[ERROR] Buy failed: {buy_resp['error']}")
            ws.close()
            return False

        print(f"[LIVE] Deriv order placed: {contract_type} {INSTRUMENT} Contract ID: {buy_resp['buy']['contract_id']} Stake ${UNITS}")
        ws.close()
        return True

    except Exception as e:
        print(f"[ERROR] Deriv exception: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="FXBOT Deriv Live Bot - Free SA No PC No $5")
    parser.add_argument("--live", action="store_true", help="Place real Deriv demo orders")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--once", action="store_true", help="Run once")
    args = parser.parse_args()

    dry_run = not args.live

    print(f"FXBOT Deriv Bot SA Free - {'DRY-RUN' if dry_run else 'LIVE DEMO'} - No PC, No $5 VPS")
    print(f"Instrument: {INSTRUMENT} Stake: ${UNITS}")
    print(f"Model: Logistic +9.8% PASS - 78 vars btc_ret_1 - Paper-trade only")
    print("-"*60)

    while True:
        now = datetime.now(timezone.utc)
        sig = get_today_signal()
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] Signal: {sig['signal']} Prob UP: {sig['prob_up']:.3f}")

        prob = sig['prob_up']
        if 0.45 <= prob <= 0.55:
            print("  -> Low confidence HOLD")
        else:
            place_deriv_order(sig['signal'], dry_run=dry_run)

        if args.once:
            break
        print("  Sleeping 15 mins...")
        time.sleep(900)

if __name__ == "__main__":
    main()
