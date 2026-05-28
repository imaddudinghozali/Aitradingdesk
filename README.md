# Imadztrades Shadow AI Trading Desk

Shadow-style XAUUSD AI Trading Intelligence Desk based on narrative delivery, DOL-first reasoning, quarterly context, and strict no-auto-entry guardrails.

The backend (FastAPI) implements the full PRD reasoning chain through execution confirmation, plus live data adapter, economic-calendar adapter, imbalance-driven IRL/ERL, an auditable analysis pipeline, and raw-candle replay. The frontend (Next.js 15 + Tailwind + Lightweight Charts) renders the dashboard pages defined in PRD Stage 13. See [frontend/README.md](frontend/README.md).
Compliance rules and deliberate boundaries are tracked in [`PRD_Compliance_Stage_0_12.md`](PRD_Compliance_Stage_0_12.md).

## Implemented Scope

- FastAPI backend scaffold
- PostgreSQL/Supabase-ready database configuration
- Environment config through `.env`
- Basic logging setup
- Health check endpoint at `/health`
- `market_snapshots` SQLAlchemy model
- Manual/webhook OHLC input for XAUUSD and XAGUSD
- Market snapshot read APIs
- UTC to NY timestamp normalization
- Yearly, monthly, weekly, Daye, and 90-minute quarter context plus Session Anchors
- Liquidity map generation for daily, weekly, monthly, yearly, Asia/London session, and evaluated news ranges
- BSL/SSL classification with active, touched, taken, and manual invalidated status
- Sweep event ledger and validation categories for touch, tap, sweep, turtle soup, manipulation, and true breakout/breakdown
- DOL assessment with primary/secondary objectives, HTF/intraday targets, engineered liquidity, and guarded lifecycle transitions
- Direction Liquidity mapping from DOL into available Monthly, Weekly, and Daily IRL/ERL layers with conflict reporting
- Market Delivery Snapshot generation through local rules or optional Claude narrative refinement
- Telegram delivery endpoint for stored narrative snapshots
- Quarter Readiness Gate that blocks premature or late execution consideration
- H4 SSMT XAU/XAG validation with CIC, sequential Daye quarters, POI gating, algorithm-context/DOL filters, and Magneto invalidation
- Structured narrative invalidation ledger with continuation, weakening, failure, and DOL-reset handling
- MMXM MMBM/MMSM context, H4 quadrant/leg grading, day filter, Judas classification, and displacement-confirmed OPR/LRLR reads
- M15 delivery tempo and expansion quality grading with explicit retracement/POI gating
- News catalyst evaluation with pre-news no-trade handling and previous-news liquidity capture
- Cross-layer delivery state and conflict-resolution output in stored narratives
- Structured `delivery_states` ledger for macro, quarterly, session, and intraday records
- Conservative POI detection for OB, FVG, IFVG, Breaker, and Mitigation confirmation
- M5/M15/H1 MSS/CISD and minimum-RR execution gate that emits setup context only
- Persisted alert records for narrative/Telegram traceability
- Trade journal API with result review and performance summaries
- Walk-forward backtest runs for stored narrative/execution decisions with session/quarter metrics
- Concept breakdowns for DOL, IRL/ERL, SSMT, Judas, OPR, MMXM, session, and quarter
- End-to-end XAUUSD analysis pipeline with ordered gate trace and missing-input reporting
- Next.js dashboard pages for narrative, DOL, IRL/ERL, SSMT, session/quarter, liquidity, ingest, calendar, alerts, journal, backtest, and replay

## Run Locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/health
```

If `DATABASE_URL` is empty, `/health` still returns app status `ok` and database status `not_configured`. Once PostgreSQL or Supabase is configured, the endpoint verifies the connection with `SELECT 1` and the app creates the initial tables on startup.

## Market Data API

```text
POST /market/ohlc
POST /market/ohlc/batch
GET  /market/latest/{symbol}/{timeframe}
GET  /market/snapshots
GET  /market/symbols
GET  /market/timeframes/{symbol}
GET  /market/status
```

## Live Market Data Ingestion

The backend supports pluggable live providers. Webhook/manual POST endpoints above remain valid; the live adapter is an additional path.

```text
POST /market/ingest/run
GET  /market/ingest/runs
GET  /market/ingest/runs/latest/{symbol}/{timeframe}
POST /market/ingest/scheduler/start
POST /market/ingest/scheduler/stop
GET  /market/ingest/scheduler/status
```

Supported providers (set `MARKET_DATA_PROVIDER`):

```text
yahoo        - free, no key; XAU via GC=F and XAG via SI=F (COMEX futures).
               H4 is aggregated from 1h (Yahoo has no native 4h). Same source
               for both metals keeps the XAU/XAG SSMT correlation clean. Recommended.
twelvedata   - REST; requires TWELVEDATA_API_KEY. Free tier serves XAU/USD only —
               XAG/USD needs a paid Grow plan, leaving SSMT without its pair.
mock         - deterministic in-memory provider for tests and offline dev
```

Configure via `.env`:

```text
MARKET_DATA_PROVIDER=twelvedata
TWELVEDATA_API_KEY=...
MARKET_INGEST_SYMBOLS=XAUUSD,XAGUSD
MARKET_INGEST_TIMEFRAMES=M5,M15,H1,H4,D
MARKET_INGEST_INTERVAL_SECONDS=300
MARKET_INGEST_AUTOSTART=false
MARKET_INGEST_AUTO_ANALYSIS=false
MARKET_INGEST_AUTO_ANALYSIS_TIMEFRAME=M15
MARKET_INGEST_AUTO_ANALYSIS_PROVIDER=rules
```

Each ingestion attempt is recorded in `ingestion_runs` (audit) with `candles_fetched`, `candles_inserted`, `candles_skipped`, `status`, and `error_message`. Dedup is by `(symbol, timeframe, timestamp_utc)`, so re-running the same window is safe. Invalid OHLC (high < low, open/close outside range) is rejected at the ingestion layer.

The scheduler is a single in-process asyncio task. `MARKET_INGEST_AUTOSTART=true` starts it on app startup; otherwise control it via the `/scheduler/*` endpoints. The currently-forming candle is dropped by providers to prevent partial-bar ingestion.

When `MARKET_INGEST_AUTO_ANALYSIS=true`, a successful batch that inserts a new XAUUSD candle on `MARKET_INGEST_AUTO_ANALYSIS_TIMEFRAME` runs the analysis pipeline once. That creates a new narrative snapshot, which can then auto-send to Telegram when `TELEGRAM_AUTO_SEND_NARRATIVE=true`. XAGUSD and non-execution timeframes do not trigger extra analysis runs, preventing duplicate Telegram messages.

Supported symbols:

```text
XAUUSD, XAGUSD
```

Supported roadmap timeframes:

```text
M5, M15, H1, H4, D
```

`Daily` and `D1` are normalized to `D`.

Every stored snapshot includes:

```text
symbol
timeframe
open
high
low
close
volume
timestamp_utc
timestamp_ny
session
session_anchor
daily_quarter
micro_quarter_90m
day_of_week
is_killzone
```

## Liquidity API

```text
POST  /liquidity/refresh
GET   /liquidity/levels
PATCH /liquidity/levels/{level_id}/status
```

`POST /liquidity/refresh` calculates liquidity from completed NY-time periods in stored market data. It returns missing level types when there is not yet enough historical daily or intraday data.

Session levels use completed `M5`, `M15`, or `H1` candles; `H4` is intentionally excluded because it can span a session boundary.

Generated level types:

```text
PDH, PDL, PWH, PWL, PMH, PML, PYH, PYL,
ASIA_HIGH, ASIA_LOW, LONDON_HIGH, LONDON_LOW,
NEWS_HIGH, NEWS_LOW (after evaluated high-impact news)
```

High levels are classified as `BSL`; low levels are classified as `SSL`. A strict penetration marks a level `taken`, an exact reach marks it `touched`, and manual invalidation is available for later narrative logic.

## Sweep Validation API

```text
POST /sweeps/scan
GET  /sweeps/events
```

`POST /sweeps/scan` inspects stored `M5`, `M15`, or `H1` candles against active liquidity levels and records:

```text
False Touch
Liquidity Tap
Valid Sweep
Turtle Soup
Manipulation Sweep
True Breakout / Breakdown
```

Basic Stage 4 timing validation treats London and NY AM interactions inside Daye Q2/Q3 as relevant sweep windows, and each sweep ledger record stores its session, anchor, daily quarter, and micro-quarter. `Manipulation Sweep` additionally requires `narrative_alignment: "aligned"` in the request; DOL evaluation now consumes confirmed events, while richer narrative alignment remains for later layers. Unconfirmed taps return `no_trade_required: true`.

## DOL API

```text
POST /dol/evaluate
GET  /dol/current/{symbol}
```

The DOL engine uses confirmed sweep displacement and active liquidity levels to identify:

```text
primary_dol
secondary_dol
htf_objective
intraday_objective
engineered_liquidity
delivery_direction
```

DOL lifecycle output:

```text
Active
Weakening
Shift Pending
Shift Confirmed
Completed
Invalidated
```

For this Stage 5 foundation, HTF untaken liquidity is preferred as the primary objective and a swept reversal level is reported as engineered liquidity. A contrary delivery event cannot replace an unresolved primary DOL: it produces `Weakening`. Shift becomes `Shift Confirmed` only when the prior objective is taken or invalidated and a new event has displacement plus relevant session/quarter timing. Stage 10 now records explicit narrative invalidation and resets DOL evaluation after confirmed failure.

## IRL / ERL Direction Liquidity API

```text
POST /direction-liquidity/evaluate
GET  /direction-liquidity/current/{symbol}
```

Stage 6 maps an active DOL into directional liquidity flow instead of returning only bullish/bearish bias:

```text
IRL -> ERL
ERL -> IRL
ERL -> IRL -> ERL
liquidity -> liquidity
```

Current hierarchy implementation:

```text
Weekly narrative: Previous Daily High/Low = IRL, Previous Weekly High/Low = ERL
Daily narrative:  Completed London/Asia High/Low = provisional IRL,
                  Previous Daily High/Low = ERL
Monthly narrative: Previous Monthly High/Low = IRL, Previous Yearly High/Low = ERL
```

The response reports per-layer status (`aligned`, `partial`, `conflict`, `waiting_dol`, `insufficient_data`), supporting timeframes, limitations, and a No Trade result whenever available direction liquidity is incomplete or conflicts with DOL.

**Imbalance flow (FR-02):** the engine inspects unmitigated `H1` / `H4` FVG and OB POI zones via `poi_zones`. When an open imbalance sits between current price and the DOL primary target in the DOL direction, the engine:

- substitutes it as an intraday IRL when the session IRL is unavailable,
- emits `imbalance -> liquidity` direction flow,
- attaches the zone reference (`poi_id`, `timeframe`, `direction`, `price_low/high`) to both the response root and the relevant layer.

If an engineered/source liquidity is `taken` and an imbalance sits opposite, the flow becomes `liquidity -> imbalance`. Invalidated POI zones and zones outside the DOL band are ignored.

## Quarter Readiness API

```text
POST /quarter-readiness/evaluate
GET  /quarter-readiness/current/{symbol}
```

Stage 8 reads the active Daye quarter from NY time, current-quarter sweep evidence, DOL, and direction liquidity alignment. It reports:

```text
Forming
Manipulation Phase
Expansion Ready
Expansion Active
Failure Risk
Closed / Late Entry
```

Only `Expansion Ready` and `Expansion Active` can pass the quarter gate, and only when DOL and direction liquidity remain aligned. Other states return `No Trade` with a specific reason and `next_valid_window`. Session anchors such as `09 NY` remain context markers and are not treated as Daye quarters.

## SSMT XAU / XAG API

```text
POST /ssmt/evaluate
GET  /ssmt/current
```

Stage 9 evaluates `XAUUSD` as the only trade asset and `XAGUSD` as its confirmation pair. The MVP reads `H4` swings aggregated into sequential Daye quarters, then validates:

```text
CIC between XAU and XAG
confirmed XAU liquidity sweep before the divergent swing
explicit POI touch confirmation
sequential quarter structure
supported market algorithm context
active DOL and direction-liquidity alignment
Magneto Effect not triggered
```

Example request after the POI has been identified externally:

```json
{
  "trade_asset": "XAUUSD",
  "confirmation_symbol": "XAGUSD",
  "timeframe": "H4",
  "poi_touched": true,
  "poi_reference": "H4 bearish FVG"
}
```

`poi_touched` remains an explicit SSMT confirmation input and may reference a zone inspected through `/execution/pois/scan`; a CIC candidate without it remains `waiting`, not valid. Divergence outside a supported modeled liquidity transition is `noise`, as required by the PRD algorithm-context filter. Magneto invalidation changes a previously valid event to `magneto_invalidated` when XAU later breaches the HTF liquidity level underlying that SSMT. The engine never suggests trading XAGUSD.

## Narrative Invalidation Ledger API

```text
POST /narrative-ledger/evaluate
GET  /narrative-ledger/current/{symbol}
```

Stage 10 registers a structured ledger automatically when `/narratives/generate` has a DOL target and an engineered invalidation level. Each active ledger stores:

```text
active_dol
target_liquidity
invalidation_level
invalidation_condition
next_decision_if_invalidated
reset_required
continuation_status
```

An incomplete narrative remains `No Trade` and is not registered as active. For an active ledger, a wick through invalidation or a single breach is treated as `weakening`; two consecutive `M15` closes through the boundary confirm `failed`, set `reset_required: true`, and move the current DOL to `Shift Pending` for fresh top-down evaluation.

## MMXM / Judas API

```text
POST /mmxm/evaluate
GET  /mmxm/current/{symbol}
```

Stage 11 uses active DOL plus an intact narrative ledger to classify contextual delivery as `MMBM`, `MMSM`, or `Neutral`. It provides:

```text
OHLC / OLHC delivery context
H4 MMXM quadrant and phase
terminus and target context
HRLR status
provisional LRLR status
OPR bounce versus true breakout/breakdown
Judas status and 09 AM context
```

`Manipulation Sweep` aligned to DOL within relevant timing can be classified as valid Judas. The specific `09 AM` profile is only claimed when London High/Low liquidity is swept. A normal reversal sweep remains `potential` until explicit manipulation evidence exists. OPR reclaim remains waiting until opposite-direction displacement confirms the bounce/rejection and agrees with DOL; LRLR remains a provisional three-swing sequence. These fields are analysis context, never a standalone trade signal.

## Delivery Quality API

```text
POST /delivery-quality/evaluate
GET  /delivery-quality/current/{symbol}
```

Stage 12 evaluates M15 candle delivery after an active narrative ledger is available. It reports:

```text
delivery tempo: compressed / slow / aggressive / delayed / exhausted expansion
expansion quality: healthy / weak / engineered / terminal expansion
clean displacement, heavy overlap, failed continuation, and target interaction flags
```

Clean directional displacement without confirmed retracement/POI is `compressed delivery` and remains `No Trade`. `/execution/evaluate` promotes validated POI reaction into this quality gate; manual evaluation remains available for reviewed evidence. Heavy overlap fails the active narrative ledger. A manipulation displacement without follow-through is `engineered expansion`; objective interaction followed by failure or an invalidated ledger is `terminal expansion`. These are explicitly `No Trade`.

## Economic Calendar API

The backend can pull high-impact events automatically and sync them into the FR-13 news catalyst gate.

```text
POST /calendar/refresh
POST /calendar/sync-to-catalyst
GET  /calendar/upcoming
POST /calendar/scheduler/start
POST /calendar/scheduler/stop
GET  /calendar/scheduler/status
```

Supported providers (set `CALENDAR_PROVIDER`):

```text
trading_economics  - Uses guest:guest free key by default; set TRADING_ECONOMICS_API_KEY to override
mock               - Deterministic provider for tests and offline dev
```

Refresh stores each event in `economic_events` keyed by `(country, event_name, scheduled_at_utc)`. Re-running upserts `actual` / `forecast` / `previous` as data lands. Relevance is decided by a configurable keyword list — default covers CPI, PCE, NFP, FOMC, Unemployment Rate, Rate Decision, and Powell Speech. `POST /calendar/sync-to-catalyst` walks every relevant high-impact upcoming event and invokes `NewsCatalystService.evaluate` for `XAUUSD`. The catalyst evaluation still requires a stored DOL assessment; when missing, the sync reports `skipped_missing_dol`. Auto-eval never produces a Valid Setup — pre-news still emits No Trade as required by FR-13.

## News Catalyst API

```text
POST /news-catalyst/evaluate
GET  /news-catalyst/current/{symbol}
```

News schedules are explicit input, not inferred. Before a high-impact event such as CPI, NFP, PCE, or FOMC, the engine marks possible pre-news liquidity engineering and blocks execution. After release it requires validated delivery quality; otherwise output remains `post_news_repricing / inconclusive`. Evaluated completed events create `NEWS_HIGH` and `NEWS_LOW` liquidity levels from the pre-release M15 range.

## Execution Confirmation API

```text
POST /execution/pois/scan
POST /execution/evaluate
GET  /execution/current/{symbol}
```

The execution layer runs only after DOL and narrative ledger context exists. It conservatively detects `FVG` and `OB` zones from three-candle displacement, records reacted OB zones as `MITIGATION`, and creates `IFVG` or `BREAKER` candidates after invalidation. A valid setup also requires current-quarter readiness, healthy delivery quality after retracement, MSS/CISD displacement confirmation, satisfied `minimum_rr`, and no blocking high-impact news state.

`Execution Status: Valid Setup` is context for discretionary trader review only. No order, position sizing, or raw buy/sell instruction is emitted.

Each execution evaluation is stored as a separate immutable history row so a later evaluation cannot rewrite the risk/target evidence used by an earlier narrative or backtest.

## Analysis Pipeline API

```text
POST /analysis/run
GET  /analysis/latest/XAUUSD
GET  /analysis/runs/{run_id}
```

`POST /analysis/run` is the operational backend entry point for the PRD decision sequence. It uses the latest stored candle on the selected execution timeframe as a decision cutoff, then runs liquidity, sweep, DOL, direction liquidity, quarter readiness, SSMT, ledger, MMXM/delivery-quality where available, execution confirmation, and the final stored narrative. Each `analysis_run` records stage statuses and missing evidence.

The pipeline executes setups only for `XAUUSD`; `XAGUSD` remains an H4 SSMT confirmation input. It is intentionally fail-closed: incomplete paired data, unreviewed SSMT POI evidence, missing ledger boundaries, or incomplete execution confirmation produces a recorded `No Trade` run rather than a fabricated setup. Narrative generation is locked to the run cutoff so later stored candles cannot change its market snapshot.

## Delivery States API

```text
GET /delivery-states/latest/{symbol}
```

Every stored narrative also writes separate macro, quarterly, session, and intraday state rows. `confidence_score` is retained as an optional database field but is not fabricated until a calibrated scoring method exists.

## Alerts And Journal API

```text
GET   /alerts
GET   /alerts/{alert_id}
POST  /journal
GET   /journal
GET   /journal/{entry_id}
PATCH /journal/{entry_id}
GET   /journal/performance
```

Every generated narrative stores an alert record, and sending it through Telegram marks that alert as delivered. Journal entries store setup context, narrative, confirmation, invalidation, risk, result, notes, and review fields. `/journal/performance` summarizes recorded outcomes by session and quarter; it is a review metric endpoint, not a look-ahead-safe historical backtest engine.

## Backtest And Refinement API

```text
POST /backtests/run
GET  /backtests
GET  /backtests/{run_id}
GET  /backtests/{run_id}/observations
GET  /backtests/{run_id}/breakdown
```

`/backtests/run` performs walk-forward scoring over stored narrative snapshots that already existed at decision time. For each snapshot with attached execution geometry, it reads only subsequent `M5`, `M15`, or `H1` candles up to `horizon_bars`, then reports:

```text
winrate
average_rr
max_drawdown_rr
best_session / worst_session
best_quarter / worst_quarter
false_ssmt_rate
false_sweep_rate
no_trade_accuracy
```

The metrics are intentionally auditable: `No Trade accuracy` is a target-versus-invalidation proxy, `false SSMT rate` uses stored Magneto-invalidated events, and `false sweep rate` measures failed resolved setups linked to confirmed source sweeps. The breakdown endpoint groups resolved setup outcomes by stored DOL, IRL/ERL, SSMT, Judas, OPR, MMXM, session, and quarter context.

## Raw-Candle Replay API

For hypothetical scenarios that were never recorded, use the replay engine. It walks raw candles chronologically and emits new shadow decisions via a pluggable policy.

```text
POST /replay/run
GET  /replay
GET  /replay/{run_id}
GET  /replay/{run_id}/decisions
```

Request example:

```json
{
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "start_utc": "2024-05-20T00:00:00Z",
  "end_utc": "2024-05-21T00:00:00Z",
  "policy": "basic",
  "step_bars": 4,
  "horizon_bars": 24
}
```

The engine guarantees **no look-ahead**: each call to the policy receives only candles up to and including `as_of_utc`, then the engine grades against strictly-later candles. The shipped `basic` policy applies Daye Quarter gating (Q2/Q3 only), sweep-and-rejection detection against an N-bar window, bias from a 20-bar SMA, and a minimum-RR check before emitting a `Valid Setup`. Add a custom policy by implementing `ReplayPolicy` and registering it through `register_replay_policy(name, factory)` — the engine treats every policy as a black box.

Persisted as `replay_runs` + `replay_decisions`. This replaces the previously deferred raw-candle replay boundary; the older decision-time `BacktestService` remains the source of truth for evaluating already-recorded decisions, while `ReplayService` is for offline what-if analysis.

## AI Narrative API

```text
POST /narratives/generate
GET  /narratives/latest/{symbol}
GET  /narratives/{narrative_id}
POST /narratives/{narrative_id}/telegram
```

Generate a deterministic Stage 7 snapshot without an external AI request:

```json
{"symbol": "XAUUSD", "provider": "rules"}
```

To let Claude refine the analytical wording, set `ANTHROPIC_API_KEY` locally and send:

```json
{"symbol": "XAUUSD", "provider": "claude"}
```

For Anthropic-compatible providers, keep `ANTHROPIC_API_FORMAT=anthropic` and use a base URL that accepts `/v1/messages`. For OpenAI-compatible routers such as AgentRouter-style gateways, use:

```env
ANTHROPIC_API_KEY="your-router-key"
ANTHROPIC_MODEL="anthropic/claude-sonnet-4-20250514"
ANTHROPIC_BASE_URL="https://agentrouter.org/v1"
ANTHROPIC_API_FORMAT="openai"
ANTHROPIC_AUTH_SCHEME="bearer"
```

If the router expects `x-api-key` instead of bearer auth, set `ANTHROPIC_AUTH_SCHEME="x-api-key"`; if unsure, `both` sends both headers.

The Claude layer may refine only delivery state and session narrative. Quarter readiness, SSMT status, MMXM/Judas classification, delivery tempo/expansion quality, news status, state conflict resolution, narrative invalidation, execution confirmation, reset actions, and target liquidity are locked by the backend. `Valid Setup` can be surfaced only from the backend confirmation gate and remains non-executable context.

Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `backend/.env`. Manual send is available through `/narratives/{narrative_id}/telegram`; set `TELEGRAM_AUTO_SEND_NARRATIVE="true"` to send every newly generated narrative snapshot automatically. Telegram messages use the Indonesian `SNAPSHOT MARKET DELIVERY` format and include quarter status, narrative status, invalidation action, and next valid window. Telegram failure never blocks snapshot persistence.

## Roadmap Discipline

This project follows the roadmap build order:

```text
Market Data -> Time / Quarter Context -> Liquidity Levels -> Sweep Validation
-> DOL Identification -> IRL / ERL Mapping -> AI Narrative -> Guardrails
```

No signal bot or auto-entry is included. `Valid Setup` remains non-executable context for discretionary trader review.
