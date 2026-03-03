"""
Trading 212 Live Portfolio Dashboard
=====================================
A real-time terminal dashboard for monitoring your Trading 212 portfolio
with analytics, P&L tracking, sector allocation, and historical snapshots.

Requirements:
    pip install requests python-dotenv rich

Usage:
    1. Add your API credentials to a .env file (see .env.example)
    2. Run: python trading212_dashboard.py

Author: Teslim Adeyanju
"""

import requests
import base64
import time
import os
import json
import csv
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.live import Live
    from rich.columns import Columns
    from rich.align import Align
    from rich import box

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────
API_KEY = os.getenv("TRADING212_API_KEY", "")
API_SECRET = os.getenv("TRADING212_API_SECRET", "")
BASE_URL = os.getenv("TRADING212_BASE_URL", "https://live.trading212.com/api/v0")
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "30"))
SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)

# ── API Client ─────────────────────────────────────────────────────────


class Trading212Client:
    """Lightweight client for the Trading 212 Public API (v0)."""

    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.base_url = base_url
        creds = f"{api_key}:{api_secret}"
        encoded = base64.b64encode(creds.encode()).decode()
        self.headers = {"Authorization": f"Basic {encoded}"}

    def _get(self, endpoint: str, params: dict = None):
        try:
            r = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                reset = e.response.headers.get("x-ratelimit-reset", "")
                print(f"  Rate limited. Resets at {reset}. Waiting...")
                time.sleep(10)
            return None
        except Exception as e:
            print(f"  API Error: {e}")
            return None

    def account_summary(self):
        return self._get("/equity/account/summary")

    def positions(self):
        return self._get("/equity/positions")

    def instruments(self):
        return self._get("/equity/metadata/instruments")

    def history_orders(self, limit=50):
        return self._paginate("/equity/history/orders", limit)

    def history_dividends(self, limit=50):
        return self._paginate("/equity/history/dividends", limit)

    def history_transactions(self, limit=50):
        return self._paginate("/equity/history/transactions", limit)

    def _paginate(self, endpoint: str, limit: int = 50):
        """Fetch all pages from a paginated endpoint."""
        all_items = []
        path = f"{endpoint}?limit={min(limit, 50)}"
        while path:
            data = self._get(path)
            if not data:
                break
            all_items.extend(data.get("items", []))
            path = data.get("nextPagePath")
            if len(all_items) >= limit:
                break
        return all_items


# ── Analytics Engine ───────────────────────────────────────────────────


class PortfolioAnalytics:
    """Computes analytics from raw position and account data."""

    def __init__(self, summary: dict, positions: list):
        self.summary = summary
        self.positions = positions
        self._enrich_positions()

    def _enrich_positions(self):
        """Add computed fields to each position."""
        total_value = sum(
            p.get("walletImpact", {}).get("currentValue", 0) for p in self.positions
        )
        for p in self.positions:
            wallet = p.get("walletImpact", {})
            cost = wallet.get("totalCost", 0)
            value = wallet.get("currentValue", 0)
            pnl = wallet.get("unrealizedProfitLoss", 0)
            p["_pnl"] = pnl
            p["_pnl_pct"] = ((value - cost) / cost * 100) if cost else 0
            p["_value"] = value
            p["_cost"] = cost
            p["_weight"] = (value / total_value * 100) if total_value else 0
            inst = p.get("instrument", {})
            p["_ticker"] = inst.get("ticker", "???")
            p["_name"] = inst.get("name", p["_ticker"])
            p["_currency"] = inst.get("currencyCode", "GBP")

    @property
    def total_value(self):
        inv = self.summary.get("investments", {})
        return self.summary.get("totalValue", 0)

    @property
    def invested(self):
        return self.summary.get("investments", {}).get("totalCost", 0)

    @property
    def total_pnl(self):
        return self.summary.get("investments", {}).get("unrealizedProfitLoss", 0)

    @property
    def total_pnl_pct(self):
        inv = self.invested
        return (self.total_pnl / inv * 100) if inv else 0

    @property
    def cash(self):
        return self.summary.get("cash", {}).get("free", 0)

    @property
    def currency(self):
        return self.summary.get("currency", "GBP")

    @property
    def winners(self):
        return sorted(
            [p for p in self.positions if p["_pnl"] > 0],
            key=lambda x: x["_pnl_pct"],
            reverse=True,
        )

    @property
    def losers(self):
        return sorted(
            [p for p in self.positions if p["_pnl"] < 0],
            key=lambda x: x["_pnl_pct"],
        )

    @property
    def win_rate(self):
        total = len(self.positions)
        wins = len(self.winners)
        return (wins / total * 100) if total else 0

    @property
    def sector_breakdown(self):
        """Group positions by sector/type."""
        sectors = {}
        for p in self.positions:
            inst = p.get("instrument", {})
            sector = inst.get("type", "Unknown")
            if sector not in sectors:
                sectors[sector] = {"value": 0, "cost": 0, "count": 0}
            sectors[sector]["value"] += p["_value"]
            sectors[sector]["cost"] += p["_cost"]
            sectors[sector]["count"] += 1
        return sectors

    @property
    def currency_exposure(self):
        """Group value by currency."""
        exposure = {}
        for p in self.positions:
            cur = p["_currency"]
            if cur not in exposure:
                exposure[cur] = 0
            exposure[cur] += p["_value"]
        return exposure

    @property
    def top_holding_weight(self):
        return max((p["_weight"] for p in self.positions), default=0)

    def concentration_warning(self, threshold=30):
        """Return positions exceeding weight threshold."""
        return [p for p in self.positions if p["_weight"] > threshold]


# ── Snapshot Manager ───────────────────────────────────────────────────


class SnapshotManager:
    """Saves daily portfolio snapshots to CSV for historical tracking."""

    def __init__(self, directory: Path = SNAPSHOT_DIR):
        self.directory = directory
        self.portfolio_file = directory / "portfolio_history.csv"
        self.positions_file = directory / "positions_history.csv"

    def save_snapshot(self, analytics: PortfolioAnalytics):
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()

        # Portfolio-level snapshot
        exists = self.portfolio_file.exists()
        with open(self.portfolio_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(
                    [
                        "date",
                        "timestamp",
                        "total_value",
                        "invested",
                        "pnl",
                        "pnl_pct",
                        "cash",
                        "positions_count",
                        "win_rate",
                    ]
                )
            writer.writerow(
                [
                    today,
                    now,
                    f"{analytics.total_value:.2f}",
                    f"{analytics.invested:.2f}",
                    f"{analytics.total_pnl:.2f}",
                    f"{analytics.total_pnl_pct:.2f}",
                    f"{analytics.cash:.2f}",
                    len(analytics.positions),
                    f"{analytics.win_rate:.1f}",
                ]
            )

        # Position-level snapshot
        exists = self.positions_file.exists()
        with open(self.positions_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(
                    [
                        "date",
                        "ticker",
                        "name",
                        "value",
                        "cost",
                        "pnl",
                        "pnl_pct",
                        "weight",
                        "currency",
                    ]
                )
            for p in analytics.positions:
                writer.writerow(
                    [
                        today,
                        p["_ticker"],
                        p["_name"],
                        f"{p['_value']:.2f}",
                        f"{p['_cost']:.2f}",
                        f"{p['_pnl']:.2f}",
                        f"{p['_pnl_pct']:.2f}",
                        f"{p['_weight']:.1f}",
                        p["_currency"],
                    ]
                )

    def load_history(self, days: int = 30):
        """Load recent portfolio history from CSV."""
        if not self.portfolio_file.exists():
            return []
        rows = []
        with open(self.portfolio_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [r for r in rows if r["date"] >= cutoff]


# ── Terminal Renderers ─────────────────────────────────────────────────


def _colour(value: float, text: str = None) -> str:
    """ANSI colour: green for positive, red for negative."""
    display = text or str(value)
    if value > 0:
        return f"\033[92m{display}\033[0m"
    elif value < 0:
        return f"\033[91m{display}\033[0m"
    return display


def _bar(pct: float, width: int = 12) -> str:
    """Mini progress bar using block characters."""
    filled = min(int(abs(pct) / 100 * width), width)
    col = "\033[92m" if pct >= 0 else "\033[91m"
    sym = "█" if pct >= 0 else "▓"
    return col + sym * filled + "░" * (width - filled) + "\033[0m"


def _sparkline_rich(values: list, width: int = 68):
    """Return a coloured Rich Text sparkline from a list of floats."""
    from rich.text import Text as RText

    blocks = "▁▂▃▄▅▆▇█"
    if len(values) < 2:
        return RText("Accumulating data…", style="dim")

    mn, mx = min(values), max(values)
    spread = mx - mn

    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = list(values)

    line = RText()
    for i, v in enumerate(sampled):
        idx = int((v - mn) / spread * 7) if spread else 3
        char = blocks[idx]
        if i == 0:
            style = "dim"
        elif sampled[i] > sampled[i - 1]:
            style = "bright_green"
        elif sampled[i] < sampled[i - 1]:
            style = "bright_red"
        else:
            style = "yellow"
        line.append(char, style=style)
    return line


def _sparkline_ansi(values: list, width: int = 60) -> str:
    """Return an ANSI-coloured sparkline string for the plain renderer."""
    blocks = "▁▂▃▄▅▆▇█"
    if len(values) < 2:
        return "[accumulating data…]"

    mn, mx = min(values), max(values)
    spread = mx - mn

    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = list(values)

    result = ""
    for i, v in enumerate(sampled):
        idx = int((v - mn) / spread * 7) if spread else 3
        char = blocks[idx]
        if i > 0 and sampled[i] > sampled[i - 1]:
            result += f"\033[92m{char}\033[0m"
        elif i > 0 and sampled[i] < sampled[i - 1]:
            result += f"\033[91m{char}\033[0m"
        else:
            result += char
    return result


def render_simple(analytics: PortfolioAnalytics, value_history=None):
    """Fallback renderer using plain ANSI escape codes."""
    os.system("cls" if os.name == "nt" else "clear")
    now = datetime.now().strftime("%d %b %Y  %H:%M:%S")
    cur = analytics.currency

    print()
    print("=" * 76)
    print(f"  TRADING 212 LIVE PORTFOLIO        {now}")
    print("=" * 76)
    print(f"  {'Total Value:':<22} {cur} {analytics.total_value:>10.2f}")
    print(f"  {'Invested:':<22} {cur} {analytics.invested:>10.2f}")
    print(f"  {'Cash:':<22} {cur} {analytics.cash:>10.2f}")
    pnl_str = f"{analytics.total_pnl:+.2f} ({analytics.total_pnl_pct:+.1f}%)"
    print(f"  {'Total P&L:':<22} {_colour(analytics.total_pnl, pnl_str)}")
    print(
        f"  {'Win Rate:':<22} {analytics.win_rate:.0f}%  "
        f"({len(analytics.winners)}W / {len(analytics.losers)}L)"
    )

    print()
    print("-" * 76)
    print(
        f"  {'STOCK':<16} {'VALUE':>9} {'COST':>9} {'P&L':>10} "
        f"{'RETURN':>8}  CHART         WT%"
    )
    print("-" * 76)

    sorted_pos = sorted(analytics.positions, key=lambda x: x["_value"], reverse=True)
    for p in sorted_pos:
        t = p["_ticker"].replace("_US_EQ", "").replace("_EQ", "")[:14]
        pnl_str = f"{p['_pnl']:>+8.2f}"
        pnl_pct_str = f"{p['_pnl_pct']:>+6.1f}%"
        print(
            f"  {t:<16} {cur}{p['_value']:>8.2f} {cur}{p['_cost']:>8.2f}  "
            f"{_colour(p['_pnl'], pnl_str)}  "
            f"{_colour(p['_pnl_pct'], pnl_pct_str)}  "
            f"{_bar(p['_pnl_pct'])}  {p['_weight']:.1f}%"
        )

    # Sector breakdown
    print()
    print("-" * 76)
    print("  SECTOR BREAKDOWN")
    print("-" * 76)
    for sector, data in analytics.sector_breakdown.items():
        pct = (data["value"] / analytics.total_value * 100) if analytics.total_value else 0
        print(f"  {sector:<20} {cur}{data['value']:>8.2f}  ({pct:>5.1f}%)  {data['count']} positions")

    # Currency exposure
    print()
    print("-" * 76)
    print("  CURRENCY EXPOSURE")
    print("-" * 76)
    for cur_code, val in analytics.currency_exposure.items():
        pct = (val / analytics.total_value * 100) if analytics.total_value else 0
        print(f"  {cur_code:<8} {cur}{val:>8.2f}  ({pct:>5.1f}%)")

    # ── Value Chart ──
    if value_history and len(value_history) >= 2:
        vals = [v for _, v in value_history]
        session_change = vals[-1] - vals[0]
        session_pct = (session_change / vals[0] * 100) if vals[0] else 0
        high, low = max(vals), min(vals)
        arrow = "▲" if session_change >= 0 else "▼"
        col = "\033[92m" if session_change >= 0 else "\033[91m"
        spark = _sparkline_ansi(vals)
        print()
        print("-" * 76)
        print("  PORTFOLIO VALUE CHART")
        print("-" * 76)
        print(f"  Lo:{cur}{low:,.2f}  {spark}  Hi:{cur}{high:,.2f}")
        print(
            f"  Session: {col}{arrow} {cur}{abs(session_change):,.2f} "
            f"({session_pct:+.1f}%)\033[0m"
            f"  |  {len(vals)} data points"
        )

    # Concentration warnings
    warnings = analytics.concentration_warning(threshold=25)
    if warnings:
        print()
        print(
            f"  \033[93m⚠  Concentration alert: "
            + ", ".join(
                f"{w['_ticker'].replace('_US_EQ','').replace('_EQ','')} "
                f"({w['_weight']:.1f}%)"
                for w in warnings
            )
            + " exceed 25% weight\033[0m"
        )

    print()
    print(
        f"  {len(analytics.positions)} positions | "
        f"Refreshes every {REFRESH_SECONDS}s | Ctrl+C to stop"
    )
    print("=" * 76)
    print()


def render_rich(analytics: PortfolioAnalytics, dividends: list = None, orders: list = None, value_history=None):
    """Rich-powered terminal renderer with tables and panels."""
    console = Console()
    console.clear()
    now = datetime.now().strftime("%d %b %Y  %H:%M:%S")
    cur = analytics.currency

    # ── Header ──
    header = Text()
    header.append("TRADING 212 ", style="bold bright_white")
    header.append("LIVE PORTFOLIO", style="bold blue")
    header.append(f"  ·  {now}", style="dim")
    console.print(Panel(Align.center(header), border_style="blue", box=box.DOUBLE))

    # ── KPI Cards ──
    pnl_style = "green" if analytics.total_pnl >= 0 else "red"
    cards = [
        Panel(
            f"[bold bright_white]{cur}{analytics.total_value:,.2f}[/]\n[dim]Total Value[/]",
            border_style="blue",
            width=22,
        ),
        Panel(
            f"[bold bright_white]{cur}{analytics.invested:,.2f}[/]\n[dim]Invested[/]",
            border_style="cyan",
            width=22,
        ),
        Panel(
            f"[bold {pnl_style}]{analytics.total_pnl:+,.2f} ({analytics.total_pnl_pct:+.1f}%)[/]\n[dim]Total P&L[/]",
            border_style=pnl_style,
            width=22,
        ),
        Panel(
            f"[bold bright_white]{cur}{analytics.cash:,.2f}[/]\n[dim]Cash ({analytics.cash / analytics.total_value * 100:.0f}%)[/]",
            border_style="yellow",
            width=22,
        ),
        Panel(
            f"[bold bright_white]{analytics.win_rate:.0f}%[/]\n[dim]{len(analytics.winners)}W / {len(analytics.losers)}L[/]",
            border_style="magenta",
            width=22,
        ),
    ]
    console.print(Columns(cards, padding=(0, 1)))

    # ── Value Chart ──
    if value_history and len(value_history) >= 2:
        vals = [v for _, v in value_history]
        session_change = vals[-1] - vals[0]
        session_pct = (session_change / vals[0] * 100) if vals[0] else 0
        high, low = max(vals), min(vals)
        change_style = "green" if session_change >= 0 else "red"
        arrow = "▲" if session_change >= 0 else "▼"

        spark = _sparkline_rich(vals)

        chart_row = Text()
        chart_row.append(f" {cur}{low:,.2f} ", style="dim")
        chart_row.append_text(spark)
        chart_row.append(f" {cur}{high:,.2f}", style="dim")

        stats_row = Text()
        stats_row.append(" Session: ", style="dim")
        stats_row.append(
            f"{arrow} {cur}{abs(session_change):,.2f} ({session_pct:+.1f}%)",
            style=f"bold {change_style}",
        )
        stats_row.append(
            f"   Hi: {cur}{high:,.2f}   Lo: {cur}{low:,.2f}   {len(vals)} pts",
            style="dim",
        )

        combined = Text()
        combined.append_text(chart_row)
        combined.append("\n")
        combined.append_text(stats_row)

        console.print(
            Panel(
                combined,
                title="[bold]Portfolio Value — Session Chart[/]",
                border_style="blue",
                padding=(0, 1),
            )
        )

    # ── Positions Table ──
    table = Table(
        title="Positions",
        box=box.SIMPLE_HEAVY,
        title_style="bold",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Ticker", style="bold", width=14)
    table.add_column("Value", justify="right", width=10)
    table.add_column("Cost", justify="right", style="dim", width=10)
    table.add_column("P&L", justify="right", width=11)
    table.add_column("Return", justify="right", width=9)
    table.add_column("Weight", justify="right", width=7)
    table.add_column("Bar", width=14)
    table.add_column("Ccy", justify="center", width=5)

    sorted_pos = sorted(analytics.positions, key=lambda x: x["_value"], reverse=True)
    for p in sorted_pos:
        t = p["_ticker"].replace("_US_EQ", "").replace("_EQ", "")
        pstyle = "green" if p["_pnl"] >= 0 else "red"
        filled = min(int(abs(p["_pnl_pct"]) / 100 * 10), 10)
        bar_char = "█" if p["_pnl"] >= 0 else "▓"
        bar_str = f"[{pstyle}]{bar_char * filled}[/][dim]{'░' * (10 - filled)}[/]"

        table.add_row(
            t,
            f"{cur}{p['_value']:.2f}",
            f"{cur}{p['_cost']:.2f}",
            f"[{pstyle}]{p['_pnl']:+.2f}[/]",
            f"[{pstyle}]{p['_pnl_pct']:+.1f}%[/]",
            f"{p['_weight']:.1f}%",
            bar_str,
            p["_currency"],
        )
    console.print(table)

    # ── Sector & Currency Side-by-Side ──
    sector_table = Table(title="Sectors", box=box.ROUNDED, title_style="bold cyan")
    sector_table.add_column("Sector", width=16)
    sector_table.add_column("Value", justify="right", width=10)
    sector_table.add_column("%", justify="right", width=7)
    sector_table.add_column("#", justify="center", width=4)
    for sector, data in analytics.sector_breakdown.items():
        pct = (data["value"] / analytics.total_value * 100) if analytics.total_value else 0
        sector_table.add_row(
            sector, f"{cur}{data['value']:.2f}", f"{pct:.1f}%", str(data["count"])
        )

    cur_table = Table(title="Currency Exposure", box=box.ROUNDED, title_style="bold yellow")
    cur_table.add_column("Currency", width=10)
    cur_table.add_column("Value", justify="right", width=10)
    cur_table.add_column("%", justify="right", width=7)
    for cur_code, val in analytics.currency_exposure.items():
        pct = (val / analytics.total_value * 100) if analytics.total_value else 0
        cur_table.add_row(cur_code, f"{cur}{val:.2f}", f"{pct:.1f}%")

    console.print(Columns([sector_table, cur_table], padding=(0, 2)))

    # ── Recent Dividends ──
    if dividends:
        div_table = Table(
            title="Recent Dividends", box=box.ROUNDED, title_style="bold green"
        )
        div_table.add_column("Date", width=12)
        div_table.add_column("Ticker", width=14)
        div_table.add_column("Amount", justify="right", width=10)
        for d in dividends[:5]:
            paid = d.get("paidOn", d.get("date", ""))[:10]
            ticker = d.get("ticker", "")
            amount = d.get("amount", 0)
            div_table.add_row(paid, ticker, f"[green]{cur}{amount:.2f}[/]")
        console.print(div_table)

    # ── Recent Orders ──
    if orders:
        ord_table = Table(
            title="Recent Orders", box=box.ROUNDED, title_style="bold magenta"
        )
        ord_table.add_column("Date", width=12)
        ord_table.add_column("Ticker", width=14)
        ord_table.add_column("Type", width=8)
        ord_table.add_column("Qty", justify="right", width=8)
        ord_table.add_column("Price", justify="right", width=10)
        ord_table.add_column("Status", width=10)
        for o in orders[:5]:
            filled = o.get("dateExecuted", o.get("dateCreated", ""))[:10]
            ticker = o.get("ticker", "")
            otype = o.get("type", "")
            qty = o.get("filledQuantity", o.get("orderedQuantity", 0))
            price = o.get("fillPrice", o.get("limitPrice", 0))
            status = o.get("status", "")
            style = "green" if float(qty or 0) > 0 else "red"
            ord_table.add_row(
                filled, ticker, otype, f"[{style}]{qty}[/]", f"{cur}{price}", status
            )
        console.print(ord_table)

    # ── Warnings ──
    warnings = analytics.concentration_warning(threshold=25)
    if warnings:
        tickers = ", ".join(
            f"{w['_ticker'].replace('_US_EQ','').replace('_EQ','')} ({w['_weight']:.1f}%)"
            for w in warnings
        )
        console.print(
            f"  [bold yellow]⚠  Concentration alert:[/] {tickers} exceed 25% weight"
        )

    console.print(
        f"\n  [dim]{len(analytics.positions)} positions · "
        f"Refreshes every {REFRESH_SECONDS}s · Ctrl+C to stop[/]\n"
    )


# ── Main Loop ──────────────────────────────────────────────────────────


def main():
    if not API_KEY or not API_SECRET:
        print("\n  ❌ Add TRADING212_API_KEY and TRADING212_API_SECRET to your .env file!")
        print("     See .env.example for reference.\n")
        return

    client = Trading212Client(API_KEY, API_SECRET, BASE_URL)
    snapshots = SnapshotManager()
    last_snapshot_date = None

    # In-session value history — seed from last 30 days of snapshots
    value_history: deque = deque(maxlen=120)
    for row in snapshots.load_history(days=30):
        try:
            dt = datetime.fromisoformat(row["timestamp"])
            value_history.append((dt, float(row["total_value"])))
        except (ValueError, KeyError):
            pass

    print("\n  🚀 Starting Trading 212 Dashboard...")
    print(f"  📡 Connecting to {BASE_URL}\n")

    while True:
        # Fetch data
        summary = client.account_summary()
        positions = client.positions()

        if not summary or positions is None:
            print(f"  ⏳ Retrying in {REFRESH_SECONDS}s...")
            time.sleep(REFRESH_SECONDS)
            continue

        analytics = PortfolioAnalytics(summary, positions or [])
        value_history.append((datetime.now(), analytics.total_value))

        # Fetch historical data (less frequently)
        dividends = None
        orders = None
        try:
            dividends = client.history_dividends(limit=10)
            orders = client.history_orders(limit=10)
        except Exception:
            pass  # Non-critical, skip if rate limited

        # Save daily snapshot
        today = datetime.now().strftime("%Y-%m-%d")
        if last_snapshot_date != today:
            snapshots.save_snapshot(analytics)
            last_snapshot_date = today

        # Render
        if RICH_AVAILABLE:
            render_rich(analytics, dividends, orders, value_history)
        else:
            render_simple(analytics, value_history)

        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  👋 Goodbye!\n")
