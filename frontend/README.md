# Imadztrades Shadow AI Trading Desk — Frontend

Next.js 15 (App Router) + TypeScript + Tailwind CSS + TradingView Lightweight Charts.

Implements PRD Stage 13 dashboard pages plus the post-roadmap engines (live market ingest, economic calendar, raw-candle replay).

## Pages

- `/` — Active Narrative Board (Market Delivery Snapshot, quarter, recent alerts)
- `/dol` — DOL Status (lifecycle gate)
- `/direction-liquidity` — IRL / ERL mapping incl. imbalance flow
- `/ssmt` — SSMT XAU/XAG (5-filter gate)
- `/session-quarter` — Daye QT + latest snapshot context
- `/liquidity` — Liquidity Map with Lightweight Charts overlay
- `/market-ingest` — Live data adapter audit + scheduler controls
- `/calendar` — Economic calendar + catalyst sync
- `/alerts` — Alert history
- `/journal` — Journal entries
- `/backtest` — Walk-forward scoring of recorded decisions
- `/replay` — Raw-candle hypothetical replay runs

All pages are read-from-backend. The backend is the source of truth; the UI never invents fields.

## Configure

```bash
cp .env.local.example .env.local
# edit NEXT_PUBLIC_API_BASE_URL if backend is not on http://127.0.0.1:8000
```

## Install & run

```bash
cd frontend
npm install
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000).

## Build

```bash
npm run build
npm run start
```

## Type-check

```bash
npm run type-check
```

## Notes

- Server components fetch from backend with `cache: "no-store"`; refresh the page to re-hit the API.
- Charting uses `lightweight-charts@^4.2.0` (MIT) — no API key, no external requests.
- Symbol picker (top-right of supported pages) writes `?symbol=` to the URL — server components re-read on navigation.
- All scheduler/ingest/calendar buttons are client components calling the backend directly. If the backend rejects (e.g. provider not configured), the inline error panel renders.
- Styling is deliberately monochrome dark + accent (`shadow-*` Tailwind palette) to match Shadow-style intent: text-dense, low chrome.
