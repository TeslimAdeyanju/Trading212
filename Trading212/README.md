# 📊 Trading 212 Live Portfolio Dashboard

A real-time terminal dashboard for monitoring your **Trading 212** ISA/Invest portfolio — with analytics, P&L tracking, sector allocation, currency exposure, dividend history, and daily snapshots.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)
![Trading 212](https://img.shields.io/badge/Trading%20212-API%20v0-green)
![License](https://img.shields.io/badge/license-MIT-brightgreen)

---

## ✨ Features

| Feature | Description |
|---|---|
| **Live Portfolio** | Real-time positions with value, cost, P&L, return %, and weight |
| **KPI Dashboard** | Total value, invested, cash balance, P&L, win rate |
| **Sector Breakdown** | Positions grouped by asset type |
| **Currency Exposure** | GBP vs USD (and other) holdings breakdown |
| **Dividend History** | Recent dividend payments from the API |
| **Order History** | Latest buy/sell orders with status |
| **Concentration Alerts** | Warnings when any position exceeds 25% weight |
| **Daily Snapshots** | Auto-saves portfolio data to CSV for historical analysis |
| **Rich Terminal UI** | Beautiful tables, panels, and colour-coded output via [Rich](https://github.com/Textualize/rich) |
| **Fallback Mode** | Works with plain ANSI colours if Rich is not installed |

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/TeslimAdeyanju/Trading212.git
cd Trading212
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up credentials

```bash
cp .env.example .env
```

Edit `.env` with your Trading 212 API Key and Secret:

```
TRADING212_API_KEY=your_api_key_here
TRADING212_API_SECRET=your_api_secret_here
```

> **How to get your API credentials:** Open the Trading 212 app → Settings → API → Generate key pair.
> See [Trading 212 Help Centre](https://helpcentre.trading212.com/hc/en-us/articles/14584770928157) for detailed instructions.

### 4. Run

```bash
python trading212_dashboard.py
```

---

## 📸 Dashboard Preview

```
╔══════════════════════════════════════════════════════════════════╗
║          TRADING 212 LIVE PORTFOLIO  ·  03 Mar 2026  19:28:25   ║
╚══════════════════════════════════════════════════════════════════╝
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ £186.52      │ │ £77.98       │ │ +7.52 (9.6%) │ │ £108.54      │
│ Total Value  │ │ Invested     │ │ Total P&L    │ │ Cash (58%)   │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

 Ticker         Value       Cost        P&L    Return  Weight  Bar
 VUAG          £23.93     £20.00      +3.93    +19.6%   25.6%  ██░░░░░░░░
 NVDA          £17.36     £18.03      -0.67     -3.7%   23.1%  ░░░░░░░░░░
 VWRP          £11.93     £10.00      +1.93    +19.3%   12.8%  █░░░░░░░░░
 ...
```

---

## 📁 Project Structure

```
Trading212/
├── trading212_dashboard.py   # Main dashboard script
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── .gitignore                # Git ignore rules
├── snapshots/                # Auto-generated daily CSV snapshots
│   ├── portfolio_history.csv
│   └── positions_history.csv
└── README.md
```

---

## 🔧 Configuration

All configuration is via environment variables (`.env` file):

| Variable | Default | Description |
|---|---|---|
| `TRADING212_API_KEY` | *(required)* | Your API Key from Trading 212 |
| `TRADING212_API_SECRET` | *(required)* | Your API Secret from Trading 212 |
| `TRADING212_BASE_URL` | `https://live.trading212.com/api/v0` | API base URL (use `demo` for paper trading) |
| `REFRESH_SECONDS` | `30` | How often to refresh data |

---

## 📈 API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `GET /equity/account/summary` | Account value, cash, P&L |
| `GET /equity/positions` | Current open positions |
| `GET /equity/history/dividends` | Dividend payment history |
| `GET /equity/history/orders` | Order execution history |
| `GET /equity/metadata/instruments` | Instrument metadata |

See the [Trading 212 API Docs](https://t212public-api-docs.redoc.ly/) for full reference.

---

## 📊 Daily Snapshots

The dashboard automatically saves a snapshot once per day to `snapshots/`:

- **`portfolio_history.csv`** — daily total value, invested, P&L, cash, win rate
- **`positions_history.csv`** — daily per-position value, cost, P&L, weight

Use these CSVs to build your own charts in Excel, Power BI, or Python.

---

## ⚠️ Limitations

- The Trading 212 API is in **beta** and only supports **Invest** and **Stocks ISA** accounts
- Multi-currency accounts show values in the primary account currency
- Rate limits apply (check `x-ratelimit-*` response headers)
- This is a **read-only** dashboard — it does not place orders

---

## 🛡️ Disclaimer

This project is **not affiliated with or endorsed by Trading 212**. Use at your own risk. The author accepts no responsibility for any financial decisions made based on this dashboard's output. Always verify data directly in the Trading 212 app.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions welcome! Feel free to open issues or pull requests.

---

**Built by [Teslim Adeyanju](https://github.com/TeslimAdeyanju)** · Chartered Accountant | Financial Data Analyst
