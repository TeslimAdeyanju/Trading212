import requests, base64, time, os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TRADING212_API_KEY", "")
API_SECRET = os.getenv("TRADING212_API_SECRET", "")

BASE_URL = "https://live.trading212.com/api/v0"
REFRESH_SECONDS = 30

def get_auth_header():
    creds = f"{API_KEY}:{API_SECRET}"
    encoded = base64.b64encode(creds.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}

def fetch(endpoint):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=get_auth_header(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error: {e}"); return None

def colour(v, t=None):
    d = t or str(v)
    if v > 0: return f"\033[92m{d}\033[0m"
    if v < 0: return f"\033[91m{d}\033[0m"
    return d

def bar(pct, w=10):
    f = min(int(abs(pct)/100*w), w)
    col = "\033[92m" if pct >= 0 else "\033[91m"
    sym = "█" if pct >= 0 else "▓"
    return col + sym*f + "░"*(w-f) + "\033[0m"

def run():
    if not API_KEY or not API_SECRET:
        print("\nAdd your API Key & Secret to the .env file!\n"); return
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        now = datetime.now().strftime("%d %b %Y  %H:%M:%S")
        summary = fetch("/equity/account/summary")
        port = fetch("/equity/positions")
        if not all([summary, port is not None]):
            print(f"Retrying in {REFRESH_SECONDS}s..."); time.sleep(REFRESH_SECONDS); continue
        cur = summary.get("currency", "GBP")
        tot = summary.get("totalValue", 0)
        investments = summary.get("investments", {})
        inv = investments.get("totalCost", 0)
        pnl = investments.get("unrealizedProfitLoss", 0)
        pct = (pnl/inv*100) if inv else 0
        print("\n" + "="*72)
        print(f"  TRADING 212 LIVE PORTFOLIO        {now}")
        print("="*72)
        print(f"  {'Total Value:':<22} {cur} {tot:>10.2f}")
        print(f"  {'Invested:':<22} {cur} {inv:>10.2f}")
        print(f"  {'Total P&L:':<22} {colour(pnl, f'{pnl:+.2f} ({pct:+.2f}%)')}")
        print("\n" + "-"*72)
        print(f"  {'STOCK':<20}{'VALUE':>10}{'P&L':>11}{'RETURN':>9}  CHART      WT%")
        print("-"*72)
        positions = sorted(port, key=lambda x: x.get("walletImpact",{}).get("currentValue",0), reverse=True)
        tc = sum(p.get("walletImpact",{}).get("totalCost",0) for p in positions)
        for p in positions:
            inst = p.get("instrument", {})
            t = inst.get("ticker","").replace("_US_EQ","").replace("_EQ","").replace("l_EQ","")[:18]
            wallet = p.get("walletImpact", {})
            v = wallet.get("currentValue", 0)
            cost = wallet.get("totalCost", 0)
            pl = wallet.get("unrealizedProfitLoss", 0)
            r = ((v - cost) / cost * 100) if cost else 0
            w = (cost / tc * 100) if tc else 0
            print(f"  {t:<20}{cur}{v:>8.2f}  {colour(pl,f'{pl:>+9.2f}')}  {colour(r,f'{r:>+7.1f}%')}  {bar(r)}  {w:.1f}%")
        print(f"\n  {len(positions)} positions | Refreshes every {REFRESH_SECONDS}s | Ctrl+C to stop")
        print("="*72 + "\n")
        time.sleep(REFRESH_SECONDS)

if __name__ == "__main__":
    try: run()
    except KeyboardInterrupt: print("\n  Goodbye!\n")

