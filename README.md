# Stock-Mate

Stock-Mate is an AI-powered portfolio dashboard that connects to your Zerodha and/or Upstox brokerage accounts and gives you a live, consolidated view of your holdings, an AI chat assistant for portfolio questions, a portfolio optimizer that turns your real holdings into concrete rebalance orders, and market analytics — performance vs. NIFTY 50 (with a "what if you'd invested in NIFTY instead" comparison), sector allocation with concentration alerts, a sector- and beta-aware portfolio health score with a shareable PNG report card, an India VIX Fear & Greed gauge, per-stock fundamentals, a market overview widget, a news digest, themed stock baskets, price alerts, and more.

## How It Works

1. **Connect your portfolio** — link your Zerodha account via Kite Connect OAuth, your Upstox account via Upstox OAuth, or both — holdings from every connected broker are merged into one consolidated view, tagged by broker
2. **Live holdings** — the dashboard pulls your current holdings, P&L, and a sector- and beta-aware portfolio health score directly from your linked broker(s), with a weighted portfolio Beta badge (Conservative/Market-aligned/Aggressive) and a one-click shareable PNG report card
3. **Market analytics** — portfolio performance is benchmarked against NIFTY 50 (with a "what if you'd invested in NIFTY instead" reality-check callout), holdings are broken down by sector with over-concentration warnings, and a market overview widget shows NIFTY 50/SENSEX levels, an India VIX Fear & Greed gauge, plus your top gainers/losers
4. **Stock financials** — click any holding to see its fundamentals (P/E, market cap, dividend yield, 52-week range, beta) alongside your own position in that stock
5. **News & baskets** — a News page shows the latest headlines for your top holdings, and a Baskets page groups stocks into curated themes (EV, Banking, IT Services, and more), highlighting which ones you already hold
6. **AI chat** — an LLM-backed assistant (Groq or OpenAI) answers portfolio questions with buy/hold/trim guidance and proactive insights, with portfolio-aware suggested prompts to get started
7. **Portfolio optimizer** — an Optimize page runs mean-variance optimization on your live holdings (Min Risk, Max Sharpe, or signal-driven Black-Litterman) and returns concrete BUY/SELL share orders, an efficient-frontier chart, a 12-month Monte Carlo projection with VaR/CVaR, and a capital-gains tax estimate on the sells; asking the chat assistant "how should I rebalance?" runs the same engine
8. **Price alerts** — set a target price and direction (above/below) for any stock from its fundamentals panel; a background job checks prices every 15 minutes and notifies you via a bell icon in the nav bar and a dedicated "My Alerts" page

## Architecture

| Component | Description |
|---|---|
| `backend_api` | FastAPI REST API — auth, portfolio, Zerodha OAuth, chat, market data, portfolio optimizer (`services/optimizer_service.py`) |
| `llm_orchestrator` | LLM reasoning layer behind the chat assistant |
| `frontend` | React + Vite web dashboard |

Data is stored in a local SQLite database (`backend_api/database/backend.db`, created automatically on first run) — no external database is required.

## Features

- **Portfolio summary** — live holdings, invested value, P&L, and a 6-factor portfolio health score (diversification, performance, risk management, concentration, sector spread, beta fit)
- **Portfolio Beta badge** — a value-weighted portfolio beta computed across your holdings' individual betas, labeled Conservative (<0.8), Market-aligned (0.8–1.2), or Aggressive (>1.2)
- **Shareable portfolio report card** — a one-click "Share" button renders your health score, total P&L, top performer, and sector allocation into a branded PNG image you can download and share, entirely client-side (no data leaves your browser)
- **Portfolio vs NIFTY 50 benchmark** — indexed performance chart (1M/3M/6M/1Y) comparing your current holdings against the NIFTY 50, using historical prices via yfinance, plus a "What if you'd invested in NIFTY 50 instead?" reality-check comparing your actual invested amount against an equivalent NIFTY-only investment over the same period
- **Sector allocation** — donut chart of holdings by sector (via yfinance), with a warning banner if any sector exceeds 40% of the portfolio
- **India VIX Fear & Greed gauge** — a live India VIX reading on the market overview widget, translated into an Extreme Greed / Greed / Neutral / Fear / Extreme Fear sentiment label
- **Stock financials panel** — click any holding to view its fundamentals (P/E ratio, market cap, dividend yield, 52-week high/low, beta) fetched from yfinance and cached daily
- **Market overview widget** — live NIFTY 50 and SENSEX levels with day change, the India VIX gauge, plus your top 5 gaining and losing holdings
- **News digest** — latest headlines for your top holdings (or a default watchlist if unlinked), fetched from yfinance and cached daily, each headline scored positive/negative/neutral via FinBERT
- **Themed stock baskets** — curated stock groupings by theme (EV, Banking, IT Services, Pharma, FMCG, and more), with your own holdings highlighted
- **AI chat assistant** — natural-language portfolio Q&A with action tags (Hold/Trim/Add/Watch/Rebalance), proactive insights, and portfolio-aware suggested prompts (diversification, riskiest holding, replacement ideas, sector exposure) to get the conversation started
- **Portfolio optimizer** — mean-variance optimization on your live merged holdings with Ledoit-Wolf covariance shrinkage and per-name weight caps; three objectives (Min Risk, Max Sharpe, and signal-driven **Black-Litterman** that turns the chat assistant's Add/Trim views into return views); outputs an interactive efficient frontier, current-vs-optimized stats, discrete BUY/SELL **share orders**, a 12-month Monte Carlo projection cone with 1-day VaR/CVaR, and a **capital-gains tax estimate** (STCG 20% / LTCG 12.5% over the ₹1.25L exemption) with a per-holding "held ≤ 1 year" toggle. The chat `rebalancing` intent runs the same optimizer and narrates the orders. Powered by `PyPortfolioOpt` + yfinance history; not investment advice.
- **Zerodha & Upstox account linking** — OAuth-based linking/unlinking for both brokers, multiple accounts per broker, primary account selection, holdings from every connected broker merged into one portfolio and badged by source
- **Price alerts** — per-stock target-price alerts with an above/below direction, one active alert per stock+direction (creating a new one replaces the old), checked automatically every 15 minutes against live prices, with a nav-bar bell notification (unread count badge, dismiss/reset actions) and a "My Alerts" management page

## Prerequisites

Install these before running the app:

- **Python 3.10+** (required — `backend_api/models/schemas.py` uses `X | None` type syntax that is not supported on Python 3.9)
- **Node.js 18+** and npm (for the Vite/React frontend)
- A **Zerodha Kite Connect** developer app (API key + secret) — [https://developers.kite.trade](https://developers.kite.trade) — needed to link a real Zerodha account
- Optional: an **Upstox** developer app (API key + secret) — [https://upstox.com/developer](https://upstox.com/developer) — needed to link a real Upstox account
- Optional: a **Groq** or **OpenAI** API key to power the AI chat assistant (the app defaults to Groq, which has a free tier)

No Docker and no external database are required to run the app locally.

## Setup

### 1. Backend

```bash
cd backend_api
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the repo root (or `backend_api/`) with at least:

```bash
# App
APP_HOST=0.0.0.0
APP_PORT=8000
FRONTEND_URL=http://localhost:5174

# Auth (change these in production)
JWT_SECRET=change-me-in-prod
BROKER_TOKEN_SECRET=change-me-too
OAUTH_STATE_HMAC_SECRET=replace-state-hmac-secret

# Zerodha Kite Connect
ZERODHA_API_KEY=your-kite-api-key
ZERODHA_API_SECRET=your-kite-api-secret
ZERODHA_REDIRECT_URL=http://localhost:8000/api/zerodha/callback

# Upstox
UPSTOX_API_KEY=your-upstox-api-key
UPSTOX_API_SECRET=your-upstox-api-secret
UPSTOX_REDIRECT_URL=http://localhost:8000/api/upstox/callback

# LLM provider for the chat assistant: "groq" (free) or "openai"
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
# OPENAI_API_KEY=your-openai-api-key

# Optional: powers the News Digest sentiment badges (FinBERT) and the chat
# assistant's knowledge retrieval (embeddings) — both call Hugging Face's hosted
# Inference API instead of loading models locally, to keep the backend light to
# host. Free token from https://huggingface.co/settings/tokens.
# Without it, news/chat still work, just without sentiment badges / RAG context.
HF_API_TOKEN=your-hf-token
```

Run the backend:

```bash
python main.py
```

The API is served at `http://localhost:8000` (docs at `/docs`).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard is served at `http://localhost:5174` and proxies API calls to the backend.

## Deploying

**Backend → Render.** `render.yaml` at the repo root defines a web service: builds
`backend_api/requirements.txt`, runs `uvicorn backend_api.app:app`. In the Render dashboard,
connect the repo, it'll pick up `render.yaml` automatically ("Blueprint" deploy), then fill
in the `sync: false` env vars (broker keys, `GROQ_API_KEY`, `HF_API_TOKEN`, `FRONTEND_URL` —
set this to your Vercel URL once you have it). Note: Render's free plan doesn't support
persistent disks, so the SQLite database resets on every redeploy/restart — fine for a demo,
not for real user data. To persist it, upgrade the service to a paid plan, add a disk
(`mountPath: /var/data`), and set `DB_PATH=/var/data/backend.db` as an env var.

**Frontend → Vercel.** Import the repo with `frontend` as the project root. Before deploying,
edit `frontend/vercel.json` and replace `YOUR-RENDER-BACKEND-URL` with your actual Render
service URL — this rewrites `/api/*` requests to the backend so the existing relative-path
`fetch("/api/...")` calls keep working unchanged and there's no CORS to configure.

## Broker notes

- Holdings from every broker you've linked (Zerodha, Upstox) are fetched and merged into a single consolidated portfolio for all analytics — sector allocation, benchmark, news digest, and stock financials all operate on the merged set automatically.
- Each holding is tagged with its source broker and shown with a small "Zerodha"/"Upstox" badge in the holdings tables.
- If you only link one broker, everything works exactly as before; if a linked broker's token expires or is invalid, that broker's holdings are simply omitted from the merge (with a reconnect prompt) rather than failing the whole page.

## Market data notes

- Historical/benchmark, sector-allocation, fundamentals, index, VIX, and news data are all fetched live from **Yahoo Finance** via `yfinance` (NSE symbols first, BSE as a fallback) — no API key required, but it does need outbound internet access.
- Sector classifications are cached in SQLite and refreshed at most once a week per symbol; stock fundamentals (including per-stock beta, used for the portfolio Beta badge) and news headlines are cached and refreshed at most once a day per symbol, to minimize external calls.
- Themed stock baskets are curated, static reference data seeded into SQLite on first run — they are not fetched from an external API and do not go stale.
- If Yahoo Finance is temporarily unreachable, the affected endpoints degrade gracefully (empty chart/panel/`data_status: market_data_unavailable`) instead of failing the whole dashboard — including the VIX gauge and Beta badge, which simply hide rather than error.

## Price alerts notes

- Set an alert from any stock's fundamentals panel (target price + Above/Below direction). Only one active alert per stock+direction per user is kept — creating another one for the same stock/direction replaces it.
- A background job (`APScheduler`, started with the FastAPI app) checks all active alerts against live prices from `yfinance` every 15 minutes. Prices are fetched once per distinct symbol per run, even if multiple alerts share a ticker.
- Triggered alerts show up as a badge count on the bell icon in the sidebar, with a dropdown to dismiss or reset them; the "My Alerts" page (`/alerts`) lists and lets you delete all of your alerts, active or triggered.
- If a price fetch fails for a symbol, that symbol is skipped for the run and the rest of the batch still runs — a fetch failure never crashes the scheduled job.

## Project Structure
```
Stock-Mate/
├── backend_api/         # FastAPI backend (auth, portfolio, Zerodha, Upstox, alerts, chat, market data)
│   ├── routes/          # API route modules (incl. alerts.py)
│   ├── services/        # Zerodha, Upstox, broker token, market data, and alert-checking services
│   ├── database/        # SQLite access layer
│   └── models/          # Pydantic request/response schemas
├── llm_orchestrator/    # LLM chat/recommendation logic
├── frontend/            # React + Vite dashboard (incl. AlertsPage, alert bell in nav)
└── tests/               # Test suite
```
