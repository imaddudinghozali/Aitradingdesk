# Imadztrade’s Implementation Roadmap

## Shadow-Style XAUUSD AI Trading Intelligence Desk

**Document type:** Markdown Implementation Roadmap  
**Purpose:** Build order untuk Claude Code, Codex, Cursor, atau developer  
**Product:** Imadztrade’s Algorithmic Delivery Interpretation Framework  
**Core model:** Shadow Quarterly Model untuk XAUUSD  
**Primary asset:** XAUUSD  
**SSMT confirmation pair:** XAGUSD  
**Important rule:** Sistem ini bukan auto-entry bot dan bukan indikator retail. Sistem ini adalah AI discretionary trading assistant berbasis narrative delivery.

---

# 1. Build Philosophy

Sistem tidak boleh dibangun dari entry signal dulu.

Urutan berpikir dan build harus mengikuti core Shadow-style logic:

```text
Market Data
↓
Time / Quarter Context
↓
Liquidity Levels
↓
Sweep Validation
↓
DOL Identification
↓
IRL / ERL Mapping
↓
AI Narrative
↓
No Trade Guardrails
↓
SSMT XAU / XAG
↓
MMXM / Judas / 09 AM Model
↓
Dashboard
↓
Journal
↓
Backtest
```

Prinsip utama:

- Jangan mulai dari AI dulu.
- Jangan mulai dari dashboard dulu.
- Jangan mulai dari auto entry.
- Jangan mulai dari FVG/MSS detector.
- Bangun dulu data, time engine, liquidity, DOL, dan narrative guardrail.

---

# 2. Stage 0 — Project Foundation

## Goal

Membuat fondasi project yang rapi dan siap dikembangkan.

## Build Tasks

- Setup repository.
- Setup backend FastAPI.
- Setup PostgreSQL atau Supabase.
- Setup environment config.
- Setup folder structure.
- Setup health check endpoint.
- Setup basic logging.
- Setup `.env.example`.

## Suggested Folder Structure

```text
imadztrades-ai-desk/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── engines/
│   │   ├── routers/
│   │   └── prompts/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
├── docs/
└── README.md
```

## Acceptance Criteria

- Server FastAPI bisa jalan.
- Endpoint `/health` mengembalikan status OK.
- Database berhasil connect.
- Project punya struktur folder awal yang jelas.

---

# 3. Stage 1 — Market Data Foundation

## Goal

Sistem bisa menerima dan menyimpan data market XAUUSD dan XAGUSD.

## Build Tasks

- Buat database entity `market_snapshots`.
- Buat input OHLC manual/webhook.
- Buat market data adapter untuk XAUUSD.
- Buat market data adapter untuk XAGUSD.
- Simpan data timeframe M5, M15, H1, H4, Daily.
- Normalisasi timestamp ke NY time dan UTC.

## Minimal Data Fields

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
```

## Acceptance Criteria

- Sistem bisa menerima data XAUUSD.
- Sistem bisa menerima data XAGUSD.
- Data tersimpan ke database.
- Data bisa dibaca ulang lewat API.

---

# 4. Stage 2 — Time Engine

## Goal

Membaca konteks waktu sesuai Shadow Quarterly dan session narrative.

## Build Tasks

- Buat NY timezone parser.
- Buat session detector:
  - Asia
  - London
  - NY AM
  - NY PM
  - London Close
- Buat Session Anchor detector:
  - 01 NY
  - 05 NY
  - 09 NY
  - 13 NY
  - 17 NY
  - 21 NY
- Buat Daye QT detector:
  - Q1: 18:00–00:00 NY
  - Q2: 00:00–06:00 NY
  - Q3: 06:00–12:00 NY
  - Q4: 12:00–18:00 NY
- Buat 90-minute micro-quarter detector.

## Important Rule

`01 / 05 / 09 / 13 / 17 / 21 NY` adalah **Session Anchor**, bukan Daily Quarter.

Daily Quarter adalah 4 quarter × 6 jam berbasis NY time.

## Acceptance Criteria

Setiap snapshot market punya informasi:

```text
session
session_anchor
daily_quarter
micro_quarter_90m
ny_time
```

---

# 5. Stage 3 — Liquidity Level Engine

## Goal

Mendeteksi liquidity level dasar sebelum masuk DOL dan AI narrative.

## Build Tasks

- Previous Daily High.
- Previous Daily Low.
- Previous Weekly High.
- Previous Weekly Low.
- Asia High / Asia Low.
- London High / London Low.
- Buyside Liquidity.
- Sellside Liquidity.
- Status liquidity:
  - active
  - touched
  - taken
  - invalidated

## Database Entity

```text
liquidity_levels
```

## Acceptance Criteria

- Sistem tahu level liquidity aktif.
- Sistem tahu level mana yang sudah taken.
- Sistem bisa membedakan BSL dan SSL dasar.

---

# 6. Stage 4 — Sweep Validation Engine

## Goal

Membedakan touch biasa dengan sweep valid.

## Sweep Categories

```text
False Touch
Liquidity Tap
Valid Sweep
Turtle Soup
Manipulation Sweep
True Breakout / Breakdown
```

## Build Tasks

- Deteksi wick touch.
- Deteksi close beyond level.
- Deteksi rejection after touch.
- Deteksi displacement after sweep.
- Deteksi failure to continue.
- Sinkronisasi sweep dengan session dan quarter.

## Valid Sweep Requirements

Sweep dianggap valid jika:

1. Level liquidity jelas.
2. Price mengambil liquidity melalui wick atau close yang valid sesuai konteks.
3. Ada rejection, displacement, atau failure to continue.
4. Terjadi pada waktu/session/quarter yang relevan.
5. Sinkron dengan DOL dan session narrative.

## Acceptance Criteria

- Sistem tidak asal menganggap wick sebagai sweep valid.
- Sistem bisa output alasan kenapa touch dianggap valid atau false.
- Sistem bisa output No Trade ketika sweep belum valid.

---

# 7. Stage 5 — DOL Engine

## Goal

Menjawab pertanyaan utama:

> Market sedang deliver ke liquidity objective mana?

## Build Tasks

- Identifikasi primary DOL.
- Identifikasi secondary DOL.
- Tentukan HTF objective.
- Tentukan intraday objective.
- Bedakan true objective vs engineered liquidity.
- Tambahkan DOL lifecycle states.

## DOL Lifecycle States

```text
Active
Weakening
Shift Pending
Shift Confirmed
Completed
Invalidated
```

## DOL Shift Rule

DOL tidak boleh berubah hanya karena price menyentuh level.

DOL baru valid jika:

1. Objective lama sudah taken atau invalidated.
2. Ada displacement/repricing ke arah baru.
3. Quarter/session mendukung perubahan delivery.
4. Narrative lama selesai atau gagal.

## Acceptance Criteria

- Sistem bisa output DOL aktif.
- Sistem bisa jelaskan kenapa DOL tersebut valid.
- Sistem bisa menolak perubahan DOL yang terlalu cepat.
- Sistem bisa output status DOL: Active, Weakening, Shift Pending, dan seterusnya.

---

# 8. Stage 6 — IRL / ERL Mapper

## Goal

Menurunkan DOL ke direction liquidity multi-timeframe.

## Build Tasks

- Monthly narrative → Weekly IRL/ERL + Daily direction liquidity.
- Weekly narrative → Daily IRL/ERL + H1/H4 direction liquidity.
- Daily narrative → H1/H4 IRL/ERL + M15/M5 direction liquidity.
- Mapping direction:
  - IRL→ERL
  - ERL→IRL
  - liquidity→liquidity
  - imbalance→liquidity
  - liquidity→imbalance

## Acceptance Criteria

- Sistem tidak cuma bilang bullish/bearish.
- Sistem bisa menjelaskan flow liquidity.
- Sistem bisa menunjukkan timeframe mana yang mendukung atau konflik.

---

# 9. Stage 7 — AI Narrative MVP

## Goal

Mulai menghubungkan logic ke GPT/Claude untuk menghasilkan narrative Shadow-style.

## Build Tasks

- Buat system prompt Shadow Delivery Reasoning.
- Buat output format Market Delivery Snapshot.
- Buat Telegram bot basic.
- Kirim hasil analisis ke Telegram.
- Tambahkan output No Trade.

## Required AI Output Format

```text
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Session: [...]
Session Anchor: [...]
Quarter (QT): [...]
HTF DOL: [...]
DOL Status: [...]
Direction Liquidity: [...]
Active Model: [...]
Delivery State: [...]
Session Narrative: [...]
Judas/Manipulation Status: [...]
SSMT XAU-XAG: [...]
Expansion Quality: [...]
Execution Status: [...]
Invalidation: [...]
Target Liquidity: [...]
```

## Acceptance Criteria

- Bot bisa kirim narasi ke Telegram.
- AI tidak langsung memberi buy/sell mentah.
- AI bisa output No Trade beserta alasan.
- Format output konsisten.

---

# 10. Stage 8 — Quarter Readiness Gate

## Goal

Mencegah entry terlalu cepat sebelum quarter jelas.

## Quarter Status States

```text
Forming
Manipulation Phase
Expansion Ready
Expansion Active
Failure Risk
Closed / Late Entry
```

## Rule

Execution hanya boleh dipertimbangkan jika quarter berada pada:

```text
Expansion Ready
Expansion Active
```

Jika quarter masih:

```text
Forming
Manipulation Phase
Failure Risk
Closed / Late Entry
```

maka sistem wajib output:

```text
No Trade
```

atau

```text
Waiting Confirmation
```

## Acceptance Criteria

- Sistem bisa menahan entry saat quarter belum siap.
- Sistem bisa menjelaskan kenapa quarter belum mendukung.
- Sistem bisa memberi next valid window.

---

# 11. Stage 9 — SSMT XAU / XAG Engine

## Goal

Mendeteksi SSMT valid, bukan noise.

## Build Tasks

- CIC detector XAU/XAG.
- Swing sequence detector.
- Quarter sequence validator.
- POI requirement.
- DOL support filter.
- Magneto Effect invalidation.
- XAU relative strength/weakness.
- Trade asset selalu XAUUSD.

## SSMT Validity Requirements

SSMT valid hanya jika:

1. Ada Crack in Correlation antara XAU dan XAG.
2. Liquidity sudah disapu.
3. Harga sudah menyentuh POI.
4. Swing terjadi di quarter berbeda secara berurutan.
5. DOL mendukung arah SSMT atau menjelaskan potensi DOL shift.
6. Tidak terkena Magneto Effect.

## Output Fields

```text
ssmt_status
ssmt_dol_alignment
ssmt_noise_status
xau_relative_state
confirmation_pair_state
trade_asset
reason_if_noise
```

## Acceptance Criteria

- Sistem bisa membedakan SSMT valid vs noise.
- Sistem tidak merekomendasikan trade di XAG.
- Sistem bisa invalidasi SSMT lewat Magneto Effect.
- Sistem bisa output alasan kenapa SSMT ditolak.

---

# 12. Stage 10 — Narrative Invalidation Ledger

## Goal

Setiap narrative punya batas batal dan keputusan setelah invalidation.

## Build Tasks

- Simpan active DOL.
- Simpan target liquidity.
- Simpan invalidation level.
- Simpan invalidation condition.
- Simpan next decision if invalidated.
- Simpan reset_required.
- Simpan narrative status.

## Narrative Status

```text
active
continuing
weakening
failed
reversed
redistributed
```

## Required Fields

```text
active_dol
target_liquidity
invalidation_level
invalidation_condition
next_decision_if_invalidated
reset_required
continuation_status
```

## Acceptance Criteria

- Setiap narrative punya invalidation.
- Jika invalidation terjadi, sistem tahu apakah harus reset DOL atau shift pending.
- Sistem tidak hanya mengganti target tanpa menjelaskan narrative failure.

---

# 13. Stage 11 — MMXM + Judas Model

## Goal

Membaca model delivery lanjutan sesuai Shadow-style.

## Build Tasks

- MMBM / MMSM recognition.
- Original consolidation.
- Accumulation / Re-accumulation.
- Distribution / Re-distribution.
- Smart Money Reversal.
- MMXM quadrant:
  - 0
  - 0.25
  - 0.5
  - 0.75
  - 1
- HRLR / LRLR logic.
- OPR Range logic.
- Judas Swing detector.
- 09 AM Model context.

## Acceptance Criteria

- Sistem bisa membaca market sebagai Buy Model atau Sell Model.
- Sistem bisa mengenali Judas sebagai engineered false directional move.
- Sistem bisa membedakan OPR bounce vs true breakdown.
- Sistem tetap tidak menjadikan MMXM sebagai sinyal mandiri.

---

# 14. Stage 12 — Delivery Quality Engine

## Goal

Mencegah sistem tertipu displacement palsu.

## Delivery Tempo

```text
compressed delivery
slow delivery
aggressive delivery
delayed expansion
exhausted expansion
```

## Expansion Quality

```text
healthy expansion
weak expansion
engineered expansion
terminal expansion
```

## Build Tasks

- Deteksi clean displacement.
- Deteksi overlap heavy.
- Deteksi failed continuation.
- Deteksi terminal expansion.
- Deteksi engineered expansion.

## Acceptance Criteria

- Sistem bisa bilang expansion valid atau belum.
- Sistem bisa output No Trade saat expansion terminal/exhausted.
- Sistem bisa membedakan manipulation move dan continuation move.

---

# Stage 12A - Backend PRD Completion (Implemented Before Dashboard)

## Goal

Menutup kontrak backend PRD sebelum membangun tampilan monitoring.

## Build Tasks

- Deteksi POI confirmation secara konservatif: FVG, OB, Mitigation, IFVG, dan Breaker.
- Validasi displacement retrace, MSS/CISD, RR minimum, news block, dan narrative/quarter gate.
- Masukkan setup context, trigger confirmation, risk context, invalidation, dan target ke narrative output.
- Simpan alert dari setiap narrative dan status pengiriman Telegram.
- Sediakan Journal API serta performance summary berdasarkan review trader.

## Acceptance Criteria

- `Valid Setup` hanya dapat muncul setelah seluruh execution gate lolos.
- Output tetap konteks analisis, tanpa auto-entry atau instruksi buy/sell.
- Alert dan journal tersimpan untuk audit.
- Historical replay/backtest penuh tetap menunggu engine bebas look-ahead.

---

# Stage 12B - Analysis Pipeline Orchestration (Implemented Before Dashboard)

## Goal

Menjalankan chain keputusan backend sebagai satu analysis run yang dapat diaudit.

## Implemented

- `POST /analysis/run` untuk urutan liquidity sampai narrative output pada cutoff candle eksekusi.
- Trace status per gate dan daftar input/evidence yang masih memblokir.
- Persisted `analysis_runs` yang menautkan DOL, mapping, quarter, SSMT, ledger, MMXM, quality, execution, dan narrative.
- Narrative cutoff guard agar run tidak membaca candle yang datang setelah waktu keputusan.

## Guardrails

- Pipeline hanya menjalankan setup `XAUUSD`; `XAGUSD` hanya confirmation pair.
- Evidence tidak lengkap menghasilkan `No Trade`, bukan setup yang dipaksakan.
- Live data/calendar scheduler dan hypothetical replay raw-candle sudah dipisah sebagai engine backend lanjutan; pipeline tetap fail-closed dan tidak mengirim order.

---

# 15. Stage 13 — Dashboard

## Goal

Membuat visual monitoring Imadztrade’s.

## Dashboard Pages

- Active Narrative Board.
- Liquidity Map.
- DOL Status.
- SSMT Status.
- Session / Quarter Status.
- Alert History.
- Journal Page.
- Backtest Page.

## Recommended Frontend

```text
Next.js
Tailwind CSS
TradingView Embed / Lightweight Charts
```

## Acceptance Criteria

- User bisa melihat DOL aktif.
- User bisa melihat session dan quarter aktif.
- User bisa melihat SSMT status.
- User bisa melihat narrative dan invalidation.

## Frontend Implementation Status

- Implemented: Active Narrative Board, Liquidity Map, DOL Status, SSMT Status, Session / Quarter Status, Alert History, Journal Page, Backtest Page.
- Added: Market Ingest, Economic Calendar, and Raw-Candle Replay pages for post-roadmap backend engines.
- Guardrail: dashboard reads backend state only; frontend does not invent trading decisions.

---

# 16. Stage 14 — Journal Engine

## Goal

Merekam reasoning trade untuk review.

## Build Tasks

- Save setup context.
- Save AI narrative.
- Save entry reason.
- Save invalidation.
- Save result.
- Save mistake review.
- Save screenshot/manual note.

## Journal Fields

```text
setup_context
entry_reason
execution_confirmation
risk
result
mistake_review
narrative_review
screenshot_path
```

## Acceptance Criteria

- Setiap setup bisa dicatat.
- Trader bisa review apakah entry sesuai narrative.
- Sistem bisa membantu menemukan mistake berulang.

---

# 17. Stage 15 — Backtest & Refinement

## Goal

Menguji framework secara historis.

## Build Tasks

- Backtest DOL.
- Backtest IRL/ERL.
- Backtest SSMT XAU/XAG.
- Backtest Judas + Quarter timing.
- Backtest OPR.
- Backtest MMXM phase.
- Review by session and quarter.

## Metrics

```text
winrate
RR average
max drawdown
best session
worst session
best quarter
worst quarter
false SSMT rate
false sweep rate
No Trade accuracy
```

## Acceptance Criteria

- Sistem bisa menguji delivery model historis.
- Trader bisa melihat setup mana yang paling reliable.
- Framework bisa diperbaiki berdasarkan data.

## Backend Implementation Status

- Implemented: walk-forward outcome scoring untuk narrative/execution snapshot yang telah tersimpan.
- Implemented: winrate, average RR, max drawdown, session/quarter ranking, false SSMT proxy, false sweep proxy, No Trade accuracy proxy, dan breakdown DOL/IRL-ERL/SSMT/Judas/OPR/MMXM.
- Implemented: raw-candle replay hypothetical dengan `ReplayService`, `ReplayPolicy`, dan basic policy no-look-ahead.
- Guardrail: assessment execution disimpan sebagai history row immutable agar keputusan lama tidak berubah.
- Boundary: replay default basic policy adalah baseline what-if engine; custom policy dapat ditambahkan tanpa mengubah engine.

---

# 18. Features That Must NOT Be Built Too Early

Jangan build fitur ini di awal:

## Auto Entry

Tidak boleh dibangun sebelum:
- DOL stabil,
- SSMT validated,
- risk engine matang,
- backtest cukup.

## Advanced Dashboard

Jangan bangun dashboard kompleks sebelum backend logic stabil.

## FVG/MSS Detector as Core

MSS/FVG hanya confirmation tools, bukan core reasoning.

## Full Backtest

Backtest penuh baru setelah DOL, IRL/ERL, SSMT, dan quarter logic stabil.

## Auto Risk Execution

Risk manager boleh dihitung, tapi auto execution jangan dulu.

---

# 19. Recommended MVP Scope

MVP pertama cukup berisi:

1. Input data XAUUSD dan XAGUSD.
2. Time Engine: session, anchor, quarter, micro-quarter.
3. Basic liquidity levels: PDH, PDL, PWH, PWL, Asia High/Low.
4. Sweep validation basic.
5. Basic DOL identification.
6. AI Narrative MVP.
7. Telegram bot output.
8. No Trade output.
9. Narrative invalidation basic.

MVP belum wajib:

- full SSMT,
- full MMXM,
- full dashboard,
- full backtest,
- auto execution,
- complex FVG/MSS detector.

---

# 20. Claude Code / Codex Build Prompt

Gunakan prompt ini untuk mulai build:

```text
You are building Imadztrade’s Algorithmic Delivery Interpretation Framework, a Shadow-style XAUUSD AI Trading Intelligence Desk.

Do not build a signal bot.
Do not build auto-entry.
Do not start from indicators.
Do not make buy/sell output without narrative.

Start from Stage 0 only:
- FastAPI backend
- PostgreSQL/Supabase database connection
- project folder structure
- health check endpoint
- market_snapshots model
- basic config and logging

Follow the roadmap strictly.
After completing each stage, stop and summarize:
1. files created
2. endpoints created
3. database models created
4. how to test
5. what is next stage

Core reasoning hierarchy:
DOL → IRL/ERL → Quarter → Session → Sweep/Judas → SSMT → Delivery Quality → Execution Confirmation.

No execution logic should be built until the data, time, liquidity, DOL, and narrative layers are ready.
```

---

# 21. Final Build Order Summary

```text
0. Project Foundation
1. Market Data Foundation
2. Time Engine
3. Liquidity Level Engine
4. Sweep Validation Engine
5. DOL Engine
6. IRL / ERL Mapper
7. AI Narrative MVP
8. Quarter Readiness Gate
9. SSMT XAU / XAG Engine
10. Narrative Invalidation Ledger
11. MMXM + Judas Model
12. Delivery Quality Engine
13. Dashboard
14. Journal
15. Backtest & Refinement
```

Final rule:

> Build intelligence before execution.  
> Build narrative before signal.  
> Build DOL before entry.
