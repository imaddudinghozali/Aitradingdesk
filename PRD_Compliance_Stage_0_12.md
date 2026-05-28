# PRD Compliance Gate - Backend Reasoning Core

Dokumen ini mencatat audit Stage 0-12 dan backend extension yang dibuat sebelum dashboard. Roadmap menentukan urutan build; PRD menentukan rule yang harus ditegakkan.

## Status

| PRD Area | Backend Status | Enforcement |
| --- | --- | --- |
| FR-01 DOL | Implemented | DOL tidak shift tanpa objective lama resolved, displacement, timing, dan narrative resolution. |
| FR-02 IRL/ERL | Implemented | Monthly/weekly/daily layers memakai PM/PY, PW/PD, dan session liquidity. Imbalance flow (`imbalance -> liquidity` / `liquidity -> imbalance`) menggunakan unmitigated FVG/OB POI di H1/H4 yang masuk band antara current price dan DOL target. |
| FR-03 / FR-03A Quarter | Implemented | Snapshot menyimpan yearly, monthly, weekly, Daye, dan 90-minute quarter; quarter gate tetap memblokir premature/late context. |
| FR-04 Session Continuation | Implemented | Narrative snapshot menyimpan session state dan inheritance narrative. |
| FR-05 Judas / 09 AM | Implemented | Judas memerlukan timed aligned manipulation; label khusus 09 AM hanya aktif untuk sweep London High/Low. |
| FR-06 / FR-06A OHLC/OLHC | Implemented as analytical context | MMXM mengeluarkan candle profile, delivery leg, weekly timing probability, dan conflict text; bukan sinyal. |
| FR-07 / FR-08 MMXM, HRLR/LRLR, OPR | Implemented | OPR reclaim wajib menunggu displacement dan DOL alignment; LRLR tetap provisional. |
| FR-08B Sweep | Implemented | Touch, tap, valid sweep, turtle soup, manipulation, dan true breakout/breakdown dibedakan. |
| FR-09 SSMT | Implemented with reviewed POI evidence | CIC, sequential quarter, swept liquidity, algorithm context, DOL alignment, dan Magneto enforced; XAG hanya confirmation pair. POI dapat direferensikan dari scanner execution. |
| FR-10 Delivery State | Implemented | Narrative output dan tabel `delivery_states` menyimpan macro, quarterly, session, intraday state, serta conflict resolution; confidence tidak dikarang tanpa calibration. |
| FR-11 Delivery Quality | Implemented | Clean drive tanpa retracement tetap compressed/No Trade; execution gate dapat memasok validated POI retracement; overlap, engineered, dan terminal behavior memblokir narrative. |
| FR-12 Narrative Failure | Implemented | Invalidation close-and-hold, SSMT conflict, blocked quarter priority, objective missed after expansion quarter, dan inefficient delivery dapat fail/reset ledger. |
| FR-13 News Catalyst | Implemented with explicit schedule input | Pre-news No Trade, post-news quality gate, dan NEWS_HIGH/NEWS_LOW dari evaluated pre-release range. |
| FR-14 Execution Confirmation | Implemented conservatively | FVG/OB/Mitigation serta invalidated IFVG/Breaker dicatat; MSS/CISD, POI reaction, quality, RR, quarter, narrative, dan news semuanya wajib lolos sebelum `Valid Setup`. Tidak ada order otomatis. |
| Output Layer - Alerts | Implemented | Setiap narrative tersimpan sebagai alert; delivery Telegram dicatat kembali pada alert. |
| Journal and Review | Implemented as backend API | Setup, confirmation, risk, result, mistake/narrative review tersimpan; ringkasan hasil tersedia per session dan quarter. |
| Backtest and Refinement | Implemented (decision-time + raw-candle replay) | `backtests` melakukan walk-forward scoring pada narrative/execution snapshot yang tersimpan. `replay` adalah engine raw-candle hypothetical: jalan kronologis melewati candle dengan policy pluggable (`basic` policy memakai Daye Q2/Q3 gate + sweep-and-rejection + min RR) tanpa look-ahead, lalu grade setiap decision terhadap candle berikutnya. Kedua engine immutable per row dan tidak menulis ulang decision lama. |
| Operational Analysis Pipeline | Implemented | `/analysis/run` menjalankan urutan gate PRD pada cutoff candle eksekusi, menyimpan trace per layer dan missing input, lalu mencatat narrative `No Trade` atau `Valid Setup` secara fail-closed. |

## Explicit Input Boundaries

- Detector POI menggunakan aturan konservatif berbasis candle untuk FVG/OB/Mitigation/IFVG/Breaker; trader tetap wajib meninjau zone tersebut.
- Jadwal high-impact news dimasukkan eksplisit melalui `/news-catalyst/evaluate`; sistem tidak mengarang kalender ekonomi.
- `Valid Setup` hanya konteks hasil gate confirmation; tidak ada order, sizing, atau rekomendasi buy/sell.
- Backtest menilai keputusan yang benar-benar tersimpan; ia tidak mengarang keputusan historis yang dahulu belum pernah direkam.
- Live market adapter sudah ada (TwelveData + Mock + in-process asyncio scheduler) dengan audit `ingestion_runs`; webhook/manual ingest tetap valid.
- Economic-calendar adapter sudah ada (TradingEconomics + Mock + asyncio scheduler) dengan upsert ke `economic_events` dan sync ke FR-13 catalyst gate untuk XAU. Auto-sync menghormati prasyarat: tidak ada DOL → `skipped_missing_dol` dan tetap No Trade.
- IRL/ERL berbasis imbalance otomatis sudah ada (FVG/OB H1/H4). Raw-candle replay engine sudah ada (`ReplayService` + `ReplayPolicy`) dengan jaminan no-look-ahead; basic policy menggunakan Daye Q2/Q3 + sweep+rejection + min RR. Custom policy dapat di-register tanpa mengubah engine.

## Regression Gate

Sebelum Stage 13 dimulai, suite backend wajib tetap lulus dan mencakup:

- unsupported SSMT algorithm context menjadi `noise`;
- OPR wick/reclaim tanpa displacement tetap `waiting`;
- clean displacement tanpa retracement tetap `compressed delivery`;
- Judas 09 AM tidak diklaim tanpa London liquidity sweep;
- SSMT conflict, overlap, terminal expansion, atau objective miss dapat menggagalkan ledger;
- pre-news dan post-news inconclusive tetap `No Trade`.
- POI reaction yang di-invalidasi kemudian tidak boleh lolos confirmation gate;
- RR yang tidak memenuhi kebijakan tetap `No Trade`;
- alert dan journal result tersimpan serta dapat direview.
- execution assessment immutable dan backtest tidak menggunakan candle sebelum snapshot keputusan.
- analysis run menyimpan trace gate dan narrative output tidak membaca candle setelah cutoff run.
