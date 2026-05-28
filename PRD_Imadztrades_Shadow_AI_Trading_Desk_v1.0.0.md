# PRD — Imadztrade’s Algorithmic Delivery Interpretation Framework

## Shadow Quarterly Model untuk XAUUSD AI Trading Intelligence Desk

**Version:** 2.1
**Changelog v2.1 (alignment ke materi Shadow Quarterly):**

- FR-03/FR-03A: Struktur quarter diluruskan ke Daye Quarterly Theory (4 quarter × 6 jam) + 90-min sebagai micro-quarter; `01/05/09/13/17/21 NY` direklasifikasi jadi Session Anchor, bukan quarter
- 5.6/FR-09: Tambah rule wajib SSMT "menyentuh POI"
- FR-02: Direction liquidity multi-TF disesuaikan (H1/H4 IRL/ERL → M15/M5)
- FR-06A: Day-of-Week close target Weekly OLHC dilengkapi (Selasa–Jumat)
- FR-09A: Definisi Magneto Effect dikunci (pemicu = SSMT mencapai HTF objective-nya sendiri)
- FR-09B: Diubah jadi Relative Strength/Weakness — XAU selalu primary instrument
- Section 5.7 + 19: Tambah definisi CISD dan Glossary

**Changelog v2.0:**

- FR-03A: Tambah Quarterly Theory Hierarchy lengkap (Yearly → Monthly → Weekly → Daily → 90min → Micro Cycles)
- FR-06A: Tambah Day-of-Week Probability untuk HTF Candle Formation
- FR-09A: Tambah Magneto Effect Invalidation logic
- FR-09B: Tambah Strong vs Weak Asset Decision Logic
- NFR: Tambah No Trade Mandatory Triggers (explicit list)  
  **Owner:** Imadztrade’s  
  **Asset utama:** XAUUSD  
  **Pair konfirmasi SSMT:** XAGUSD  
  **Product type:** AI discretionary trading assistant, bukan auto-entry bot dan bukan indikator retail.

-----

## 1. Product Vision

Imadztrade’s dibangun sebagai **AI trading intelligence desk** yang membaca market berdasarkan cara pikir Shadow Quarterly: market dipahami sebagai proses **algorithmic price delivery** yang bergerak dari satu liquidity objective ke objective lain melalui time cycle, engineered liquidity, manipulation, expansion, repricing, dan continuation.

Produk ini tidak bertujuan memberi sinyal buy/sell mentah. Tujuannya adalah membantu trader discretionary memahami **DOL (Draw on Liquidity), IRL/ERL, quarterly delivery, SSMT, MMXM, Judas Swing, OHLC/OLHC delivery**, dan kondisi valid atau gagalnya sebuah narrative market.

-----

## 2. Core Philosophy

Sistem tidak boleh membaca market dari indikator, trendline, candle pattern, atau setup hunting retail. Sistem harus membaca market dari pertanyaan inti:

> “Price sedang di-deliver ke liquidity objective mana, melalui quarter dan session apa, dengan bentuk manipulation atau expansion seperti apa?”

Semua fitur harus tunduk pada DOL dan narrative delivery. Execution confirmation seperti MSS, FVG, IFVG, breaker, atau mitigation hanya boleh dipakai sebagai validasi tambahan, bukan alasan utama entry.

-----

## 3. Root Model — DOL First

DOL adalah akar seluruh interpretasi. Sistem harus selalu mulai dari identifikasi liquidity objective paling dominan.

Urutan berpikir utama:

1. Tentukan HTF liquidity objective.
1. Tentukan apakah market sedang IRL to ERL, ERL to IRL, liquidity to liquidity, imbalance to liquidity, atau liquidity to imbalance.
1. Turunkan narrative ke quarterly delivery.
1. Turunkan lagi ke session narrative.
1. Baru cari confirmation pada intraday/execution timeframe.

Prinsip penting: **execution tidak boleh mendahului DOL**.

-----

## 4. Shadow Delivery Hierarchy

Hierarki interpretasi yang wajib diikuti sistem:

```text
HTF Liquidity Objective
↓
Direction Liquidity / IRL-ERL Mapping
↓
Quarterly Delivery State
↓
Session Continuation Narrative
↓
Liquidity Engineering / Judas Swing
↓
Expansion or Repricing Confirmation
↓
Execution Confirmation
```

Kalau terjadi konflik antar timeframe, sistem harus menyelesaikan konflik dengan priority model, bukan langsung memberi sinyal.

-----

## 5. Source Concepts yang Wajib Diadopsi

### 5.1 Framework Universal Model

Sistem harus mengenali tiga model dasar:

1. **Internal to External**  
   Market meninggalkan imbalance, lalu retrace ke imbalance untuk melanjutkan ekspansi menuju external range liquidity.
1. **External to Internal**  
   Market mengambil external liquidity, lalu retrace ke imbalance/internal range sebelum melanjutkan ekspansi.
1. **OPR (Order Pairing Ranges)**  
   Market membentuk range, salah satu sisi range diambil, lalu potensi delivery bergerak ke sisi berlawanan.

### 5.2 Liquidity HTF dan LTF

Sistem harus membaca previous liquidity dari high/low candle HTF seperti daily, weekly, monthly, yearly, previous session, dan previous news. Pada LTF, liquidity HTF divisualkan sebagai buyside/sellside liquidity, turtle soup, atau liquidity run.

### 5.3 HRLR dan LRLR

Sistem harus membedakan:

- **HRLR (High Resistance Liquidity Run):** harga sengaja dijalankan di atas/bawah strong swing point untuk manipulasi, bukan selalu untuk continuation.
- **LRLR (Low Resistance Liquidity Run):** penumpukan liquidity seperti trendline liquidity yang dapat menjadi target setelah HRLR diambil.

Aturan operasional: setelah HRLR diambil, sistem mencari liquidity berikutnya yang paling masuk akal sebagai target, termasuk LRLR jika narrative mendukung.

### 5.4 OHLC dan OLHC Delivery

Sistem harus membaca pembentukan candle HTF sebagai delivery model:

- **OHLC:** Open → High → Low → Close
- **OLHC:** Open → Low → High → Close

Setiap candle HTF memiliki proses opportunity:

1. Open to High
1. High to Low
1. Low to Close

Vice versa untuk OLHC.

### 5.5 MMXM Model

MMXM dipakai untuk mengetahui apakah market berada dalam Buy Model atau Sell Model, bukan sebagai sinyal mandiri. Sistem harus memahami fase:

- Original consolidation
- Accumulation
- Re-accumulation
- Smart Money Reversal
- Distribution
- Re-distribution
- Expansion menuju liquidity objective

MMXM Swing Grading menggunakan quadrant 0, 0.25, 0.5, 0.75, 1 untuk membaca fase dan posisi delivery.

### 5.6 SSMT

SSMT digunakan sebagai confluence setelah liquidity diambil. Untuk XAUUSD, pair utama adalah **XAGUSD**. Sistem tidak boleh menganggap semua divergence sebagai sinyal.

Prasyarat: ada **Crack in Correlation (CIC)** antara XAU dan XAG.

SSMT valid hanya jika **semua** rule berikut terpenuhi (per materi C.1):

1. Liquidity sudah disapu (IRL / ERL / Buyside / Sellside).
1. **Harga sudah menyentuh POI.**
1. Terbentuk 2 swing divergent di **quarter berbeda secara berurutan** (bukan dalam satu quarter yang sama, tidak loncat quarter).
1. Baru akan di-deliver ke liquidity berikutnya / sesuai market algorithm.

SSMT membantu membaca relative strength/weakness, reversal potential, atau delivery ke liquidity berikutnya.

### 5.7 CISD (Change in State of Delivery)

CISD adalah perubahan kondisi delivery — dari manipulation ke expansion, atau dari continuation ke failure. Sistem memakai CISD sebagai konfirmasi entry di LTF (materi Shadow Generation hal. 35: "Entry = CISD").

Catatan implementasi: materi juga memakai singkatan **CSD** di quadrant 0.5 MMXM Swing Grading. Perlakukan CSD dan CISD sebagai konsep yang sama (shift state of delivery) kecuali didefinisikan beda secara eksplisit. CISD bukan trigger entry mandiri — ia hanya muncul setelah narrative dan POI valid.

-----

## 6. Functional Requirements

### FR-01 — DOL Identification

Sistem harus menentukan DOL aktif dengan input data multi-timeframe. Output minimal:

- Primary DOL
- Secondary DOL
- HTF objective
- Intraday objective
- alasan liquidity tersebut dianggap valid
- apakah liquidity tersebut true objective atau engineered liquidity
- DOL lifecycle status (lihat di bawah)

**DOL Lifecycle Status:**

```text
Active          — DOL jelas, narrative mendukung, belum ada tanda perubahan
Weakening       — DOL belum dicapai tapi quarter/session gagal expand ke arahnya
Shift Pending   — ada indikasi DOL baru (liquidity lama diambil, displacement muncul),
                  tapi konfirmasi belum selesai
Shift Confirmed — semua 4 kondisi shift terpenuhi, DOL resmi berganti
Invalidated     — DOL terbukti bukan objective valid (false DOL / engineered)
```

**DOL hanya boleh dinyatakan berubah jika semua kondisi ini terpenuhi:**

1. Liquidity objective lama sudah taken (bukan hanya touched).
2. Ada displacement / repricing bersih ke arah DOL baru.
3. Quarter dan session aktif mendukung delivery ke DOL baru.
4. Narrative lama sudah berstatus `failed` atau `completed`.

Sistem tidak boleh mengubah DOL hanya karena price menyentuh level atau ada candle besar tunggal.

### FR-02 — IRL/ERL Direction Liquidity Mapping

Sistem harus memetakan IRL dan ERL sesuai timeframe. Ketentuan:

- Monthly narrative diturunkan ke Weekly IRL/ERL dan Daily direction liquidity (buyside/sellside).
- Weekly narrative diturunkan ke Daily IRL/ERL dan H1/H4 direction liquidity.
- Daily narrative diturunkan ke H1/H4 IRL/ERL serta M15/M5 direction liquidity.

Output harus menjelaskan apakah market sedang IRL→ERL, ERL→IRL, liquidity→liquidity, imbalance→liquidity, atau liquidity→imbalance.

### FR-03 — Quarterly Delivery Interpretation

Quarterly bukan sekadar blok waktu. Sistem harus membaca quarter sebagai transition state. Sistem harus menentukan:

- quarter intent
- quarter continuation
- quarter manipulation
- quarter expansion
- quarter failure
- quarter reversal

**Quarter Status (Quarter Readiness Gate):**

```text
Forming           — quarter baru dimulai, intent belum jelas
Manipulation Phase — quarter sedang mengambil liquidity satu arah sebagai setup
Expansion Ready   — manipulation selesai, displacement awal muncul, menunggu konfirmasi
Expansion Active  — expansion berlangsung, delivery ke DOL aktif
Failure Risk      — expansion gagal continue, potensi reversal atau redistribution
Closed / Late Entry — quarter hampir tutup, entry baru terlalu berisiko
```

**Entry hanya boleh dipertimbangkan jika:**

1. Quarter Status minimal `Expansion Ready`.
2. Quarter intent mendukung DOL aktif.
3. Manipulation sudah terjadi atau narrative menunjukkan tidak diperlukan.
4. Expansion confirmation (displacement / CISD) sudah muncul.

Jika Quarter Status masih `Forming` atau `Manipulation Phase`, sistem wajib output `No Trade — quarter belum siap`.

**Catatan struktur:** Timing `01 / 05 / 09 / 13 / 17 / 21 NY` adalah **Session Reference Anchors** (titik acuan killzone/session), **bukan** quarter Quarterly Theory. Untuk QT dan validasi SSMT, gunakan struktur 4-quarter Daye di FR-03A. Dua konsep ini wajib dipisah agar logika SSMT konsisten.

Session Reference Anchors (konteks narrative):

- 01 NY — Asia close / London pre-market
- 05 NY — London open
- 09 NY — NY open / killzone
- 13 NY — NY mid-session
- 17 NY — London close
- 21 NY — Asia open

#### FR-03A — Quarterly Theory Hierarchy (Full Cycle)

Quarterly Theory memiliki hierarki dari macro ke micro. Sistem harus memahami dan membaca semua level ini karena validasi SSMT dan delivery narrative bergantung pada quarter mana swing terbentuk di setiap level.

```text
Yearly Quarters (Q1–Q4)
↓
Monthly Quarters (Q1–Q4 = 4 minggu)
↓
Weekly Quarters (Q1–Q4 = Senin–Kamis/Jumat)
↓
Daily Quarters (Q1–Q4 × 6 jam, Daye QT)
  Q1: 18:00–00:00 NY | Q2: 00:00–06:00 NY
  Q3: 06:00–12:00 NY | Q4: 12:00–18:00 NY
  [Session Anchors: 01/05/09/13/17/21 NY — bukan quarter QT]
↓
90-Minute Micro-Quarters (4 × 90 min per Daily Quarter)
↓
Micro Cycles
```

**Aturan operasional per level:**

**Yearly Quarters (Q1/Q2/Q3/Q4):**

- Q1: Jan–Mar | Q2: Apr–Jun | Q3: Jul–Sep | Q4: Oct–Dec
- Digunakan untuk membaca macro DOL dan narrative tahunan

**Monthly Quarters:**

- Setiap bulan dibagi 4 minggu
- Minggu 1: liquidity build / accumulation
- Minggu 2: CPI/data catalyst — potential manipulation
- Minggu 3: FOMC/major event — potential expansion
- Minggu 4: distribution / repositioning

**Weekly Quarters (Day-based):**

- Q1: Senin | Q2: Selasa | Q3: Rabu | Q4: Kamis–Jumat
- Digunakan untuk pembentukan Low/High of the Week

**Daily Quarters (Daye QT — 4 quarter × 6 jam, NY Time, true day open 18:00):**

- Q1: 18:00–00:00 NY (Asia)
- Q2: 00:00–06:00 NY (London)
- Q3: 06:00–12:00 NY (NY AM)
- Q4: 12:00–18:00 NY (NY PM)

**90-Minute Micro-Quarters:**

- Setiap Daily Quarter (6 jam) dibagi menjadi 4 micro-quarter × 90 menit (360 ÷ 4 = 90, membagi utuh)
- Digunakan untuk precision entry di LTF (M5/M15) dan membaca manipulation vs expansion di dalam satu quarter aktif
- 90-min adalah sub-divisi dari quarter 6-jam, bukan pembagian dari 4H candle

**Validasi SSMT berbasis Quarterly Hierarchy (wajib pakai struktur 4-quarter Daye):**

- Swing 1 dan Swing 2 harus berada di quarter berbeda secara berurutan (Q1→Q2, Q2→Q3, dst) di level timeframe yang digunakan
- Tidak boleh dalam 1 quarter yang sama
- Tidak boleh loncat quarter (Q1 → Q3 tanpa Q2)
- Validasi dilakukan di level QT yang sesuai dengan TF analisa (contoh: H4 SSMT → validasi di Daily Quarter; H1 SSMT → validasi di 90-min micro-quarter)

### FR-04 — Session Continuation Narrative

Sistem harus memahami inheritance antar session:

- Asia membentuk range atau liquidity build-up.
- London dapat menjadi manipulation/Judas atau continuation awal.
- NY dapat menjadi expansion, repricing, atau reversal setelah London liquidity diambil.
- London Close dapat menjadi continuation failure atau reversal delivery.

Output harus menjelaskan narrative yang diwariskan dari session sebelumnya ke session aktif.

### FR-05 — Judas Swing Detection

Sistem harus mendeteksi Judas Swing sebagai engineered false directional move. Judas tidak boleh dibaca hanya sebagai sweep biasa. Judas valid jika:

- terjadi di area waktu yang relevan,
- menyapu liquidity tertentu,
- gagal continue ke arah sweep,
- menghasilkan displacement atau shift menuju objective berlawanan,
- sinkron dengan DOL dan session narrative.

Khusus 09 AM Model, sistem harus memperhatikan kondisi ketika sekitar 09:00 NY price masuk key level dan menyapu liquidity London session, lalu mencari reversal profile atau continuation profile.

### FR-06 — OHLC/OLHC HTF Candle Builder

Sistem harus menginterpretasi intraday movement sebagai proses membangun candle HTF. Output harus menjawab:

- candle HTF sedang cenderung OHLC atau OLHC,
- posisi harga sekarang berada pada Open→High, High→Low, atau Low→Close,
- liquidity mana yang perlu diambil agar candle HTF selesai,
- apakah current move adalah manipulation leg atau expansion leg.

#### FR-06A — Day-of-Week Probability untuk HTF Candle Formation

Opportunity OHLC/OLHC harus dikaitkan dengan hari dalam seminggu sebagai time filter. Sistem harus memahami probabilitas pembentukan titik High/Low berdasarkan posisi hari dalam weekly candle:

**Weekly OLHC (Bullish Weekly):**

- Low of the Week (dari opening) cenderung terbentuk: Senin, Selasa, atau Rabu
- High of the Week (Close target) cenderung terbentuk: Selasa, Rabu, Kamis, atau Jumat
- Opportunity: Open→Low (Mon–Wed), Low→High (Tue–Fri)

**Weekly OHLC (Bearish Weekly):**

- High of the Week cenderung terbentuk: Senin, Selasa, atau Rabu
- Low of the Week (Close target) cenderung terbentuk: Selasa, Rabu, Kamis, atau Jumat
- Opportunity: Open→High (Mon–Wed), High→Low (Tue–Fri)

**Aturan operasional:**

- Sistem tidak boleh mengasumsikan Low of the Day otomatis mendukung Low of the Week
- Sistem tidak boleh mengasumsikan Low of the Week otomatis mendukung Low of the Month
- Setiap level opportunity harus divalidasi dengan HTF IRL/ERL yang mendukung
- Jika hari tidak mendukung pembentukan target (misal mencari Low di Jumat tanpa ERL), sistem harus output status “timing conflict”

**Output tambahan FR-06A:**

- hari aktif dalam weekly candle (Mon/Tue/Wed/Thu/Fri),
- probabilitas formation (early week / mid week / late week),
- apakah timing mendukung Low to Close, Open to Low, High to Close, atau Open to High,
- conflict flag jika hari tidak sesuai dengan target delivery.

### FR-07 — MMXM Buy/Sell Model Recognition

Sistem harus menentukan apakah market lebih cocok dibaca sebagai MMBM atau MMSM. Output minimal:

- model aktif: Buy Model / Sell Model / belum valid,
- titik terminus,
- fase swing grading,
- area accumulation, re-accumulation, distribution, re-distribution,
- target liquidity akhir.

### FR-08 — HRLR/LRLR Liquidity Run Logic

Sistem harus mendeteksi apakah harga sedang mengambil HRLR atau membangun LRLR. Output:

- HRLR yang sudah diambil,
- LRLR yang menjadi target potensial,
- apakah sweep adalah manipulation atau true expansion,
- target liquidity setelah run.

### FR-08B — Sweep Validation Engine

Tidak semua sentuhan ke level liquidity adalah sweep yang valid. Sistem harus mengklasifikasikan setiap interaksi harga dengan level liquidity ke dalam kategori berikut.

**Sweep valid hanya jika semua kondisi terpenuhi:**

1. Level liquidity jelas dan terdaftar sebagai active level.
2. Price benar-benar mengambil liquidity (menembus level, bukan hanya menyentuh).
3. Rejection atau displacement muncul setelah sweep.
4. Sweep terjadi di session anchor / quarter yang relevan.
5. Sweep sinkron dengan DOL aktif dan session narrative.

**Sweep Status:**

```text
False Touch       — price menyentuh area level tapi tidak mengambil liquidity,
                    tidak ada reaction signifikan
Liquidity Tap     — price masuk ke liquidity zone tapi belum ada displacement,
                    menunggu konfirmasi
Valid Sweep       — liquidity diambil + ada displacement reversal yang bersih
Turtle Soup       — wick sweep di bawah/atas level, candle close kembali ke atas/bawah,
                    ini adalah setup reversal klasik (valid liquidity taken)
Manipulation Sweep — sweep yang disengaja sebagai engineered liquidity sebelum
                     expansion ke arah berlawanan (sinkron dengan Judas / DOL)
```

**Aturan penting:**

- `False Touch` dan `Liquidity Tap` tidak boleh dipakai sebagai konfirmasi DOL taken.
- `Turtle Soup` dianggap valid sweep meskipun hanya wick — kriterianya adalah **candle close kembali di atas/bawah level setelah wick**, bukan close di luar level.
- `Manipulation Sweep` harus sinkron dengan DOL, session narrative, dan quarter intent agar tidak dianggap sebagai true breakdown.

Output FR-08B harus mencakup:

- Sweep Status aktif (dari kategori di atas),
- level yang disweep,
- apakah konfirmasi displacement sudah ada atau masih waiting,
- target liquidity setelah sweep selesai.

### FR-09 — SSMT XAU/XAG Engine

Sistem hanya menggunakan XAGUSD sebagai pair SSMT utama untuk XAUUSD. DXY dan US10Y boleh menjadi macro pressure filter, tetapi bukan SSMT.

Output SSMT harus mencakup:

- apakah XAU dan XAG crack in correlation,
- quarter swing sequence valid atau tidak,
- XAU relative state (relative_strength / relative_weakness / neutral),
- apakah SSMT mendukung reversal, continuation, atau hanya noise,
- liquidity apa yang sudah diambil sebelum SSMT terbentuk.

#### FR-09A — Magneto Effect Invalidation

SSMT yang sudah terbentuk dapat kehilangan validitasnya melalui Magneto Effect. Sistem harus mendeteksi dan menangani kondisi ini.

**Definisi Magneto Effect:**
Magneto Effect terjadi ketika level SSMT yang sudah terbentuk mencapai / diambil sebagai HTF liquidity objective-nya sendiri. Pada titik itu SSMT tersebut "terpakai habis", berubah menjadi liquidity baru, dan tidak lagi berlaku sebagai sinyal reversal.

**Prinsip penting:** Magneto Effect tidak otomatis membatalkan semua SSMT. Selama draw HTF yang mendasari SSMT belum tersentuh, SSMT tetap valid. (Materi C.1: pada pasangan SSMT atas-bawah, sisi yang sudah menyentuh HTF liquidity-nya menjadi liquidity baru; sisi yang belum tetap aktif.)

**Trigger Magneto Effect:**

- Level SSMT mencapai / diambil sebagai HTF liquidity objective-nya
- Pada pasangan SSMT: sisi yang sudah menyentuh HTF liquidity-nya menjadi liquidity baru; sisi yang belum tetap valid

**BUKAN trigger (cegah over-invalidasi):**

- Wick menembus level SSMT tanpa close dan tanpa mencapai HTF objective
- Pullback biasa yang belum menyentuh draw HTF

**Aturan operasional:**

- Sistem harus tracking status setiap SSMT event secara aktif
- Ketika Magneto Effect terpicu, sistem harus update `ssmt_events.status = 'magneto_invalidated'`
- Sistem wajib output alert “SSMT Invalidated via Magneto Effect” beserta level yang menjadi liquidity baru
- SSMT yang ter-invalidasi tidak boleh dipakai sebagai konfirmasi entry

**Output tambahan FR-09A:**

- status Magneto Effect: active / triggered / clear,
- level SSMT yang berubah menjadi liquidity baru,
- DOL baru yang terbentuk setelah Magneto Effect.

#### FR-09B — Relative Strength/Weakness & Instrument Decision

Trade decision selalu pada XAU sebagai primary instrument. XAG hanya confirmation pair. SSMT XAU/XAG dipakai untuk membaca apakah XAU menunjukkan relative weakness atau relative strength setelah liquidity event — bukan untuk memilih instrument yang "strong" atau "weak".

**Logic:**

- **Bullish SSMT** (XAU Higher Low, XAG Lower Low): XAU menunjukkan relative strength → bias long XAU
- **Bearish SSMT** (XAU Lower High, XAG Higher High): XAU menunjukkan relative weakness → bias short XAU

**Aturan operasional:**

- Sistem tidak boleh merekomendasikan trade di XAG
- SSMT murni dipakai sebagai confluence untuk membaca kondisi XAU, bukan pemilih instrument
- Output harus eksplisit menyebut instrument dan alasan: “Trade Asset: XAU | Reason: XAU adalah primary instrument; XAG hanya confirmation pair.”

**Output tambahan FR-09B:**

- relative read XAU (relative strength / relative weakness),
- instrument yang di-trade (selalu XAU),
- alasan berbasis narrative.

#### FR-09C — Market Algorithm Context Check

SSMT hanya valid jika market algorithm state mendukung terbentuknya SSMT. Divergence yang muncul di luar konteks algorithm yang benar harus diklasifikasikan sebagai noise atau liquidity, bukan sinyal reversal.

**Market algorithm states yang mendukung SSMT:**

- `imbalance → liquidity` — price bergerak dari imbalance menuju liquidity (SSMT bisa muncul di titik liquidity)
- `liquidity → liquidity` — price berpindah dari satu liquidity ke liquidity berikutnya (SSMT valid di transisi)
- `liquidity → imbalance` — price retrace ke imbalance setelah liquidity diambil (SSMT bisa konfirmasi retrace)

**Algorithm states yang TIDAK mendukung SSMT:**

- Price masih di tengah range tanpa bias jelas (no man's land)
- SSMT muncul sebelum ada liquidity yang diambil
- Algorithm state bertentangan dengan arah SSMT (misal: algorithm masih `imb → liq` bullish tapi SSMT bearish terbentuk)

**Aturan operasional:**

- Sistem harus evaluasi algorithm state sebelum memvalidasi SSMT.
- Jika algorithm state tidak mendukung, sistem output: `SSMT Status: Noise — algorithm context tidak mendukung`.
- Ini adalah layer ke-5 validasi SSMT (melengkapi 4 rules dari FR-09 dan FR-09C menjadi 5 filter wajib).

### FR-10 — Delivery State Tracking

Sistem harus menilai state market pada macro, quarterly, session, dan intraday:

- accumulation
- manipulation
- expansion
- repricing
- continuation
- exhaustion
- redistribution

Jika state bertentangan, sistem wajib menampilkan conflict resolution.

### FR-11 — Delivery Tempo and Expansion Quality

Sistem harus membaca tempo:

- compressed delivery
- slow delivery
- aggressive delivery
- delayed expansion
- exhausted expansion

Sistem juga harus menilai kualitas expansion:

- healthy expansion
- weak expansion
- engineered expansion
- terminal expansion

Tidak semua displacement valid sebagai continuation.

### FR-12 — Narrative Continuation and Failure

Sistem harus menyimpan active narrative dan memperbarui statusnya:

- active
- continuing
- weakening
- failed
- reversed
- redistributed

Narrative dianggap gagal jika:

- liquidity objective gagal dicapai setelah expansion,
- price reclaim area invalidation,
- quarter transition mengubah delivery priority,
- SSMT bertentangan dengan DOL aktif,
- expansion berubah menjadi overlap/inefficient delivery.

**Narrative Invalidation Ledger (wajib diisi untuk setiap narrative aktif):**

Setiap narrative yang disimpan sistem harus memiliki semua field berikut sebelum dianggap valid:

```text
1. active_dol           — DOL yang sedang dituju
2. target_liquidity     — level liquidity target akhir
3. invalidation_level   — level harga yang jika ditembus membatalkan narrative
4. invalidation_condition — kondisi spesifik (misal: "M15 close dan hold di atas London High")
5. narrative_status     — active / weakening / failed / reversed / redistributed
6. next_decision        — langkah berikutnya jika narrative invalidated
                          (misal: "reset DOL ke BSL atas, mulai top-down analysis baru")
```

Sistem tidak boleh menyimpan narrative aktif tanpa `invalidation_level` dan `next_decision`. Jika field ini kosong, sistem harus output: `Narrative incomplete — invalidation belum didefinisikan. No Trade.`

### FR-13 — News Delivery Catalyst

News tidak dianggap sebagai sinyal random. News dipakai sebagai delivery catalyst untuk:

- pre-news accumulation,
- liquidity engineering,
- fake expansion,
- post-news repricing,
- continuation menuju DOL.

News utama:

- CPI
- PCE
- NFP
- FOMC
- unemployment data
- rate decision / speech penting

### FR-14 — Execution Confirmation

Execution hanya boleh muncul jika narrative sudah valid. Confirmation tools:

- MSS
- FVG
- IFVG
- breaker
- mitigation
- displacement retrace

Output execution harus berisi:

- setup context,
- trigger confirmation,
- invalidation,
- target liquidity,
- reason no-trade jika belum valid.

-----

## 7. AI Reasoning Contract

Setiap analisis AI wajib mengikuti urutan:

1. HTF DOL
1. IRL/ERL direction liquidity
1. quarterly delivery state
1. session continuation
1. liquidity engineering / Judas
1. SSMT XAU/XAG
1. delivery tempo
1. expansion quality
1. execution confirmation
1. invalidation dan no-trade condition

AI dilarang langsung memberi buy/sell sebelum seluruh context utama dibaca.

-----

## 8. Required AI Output Format

Setiap alert atau analisis harus menghasilkan format:

```text
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Session: [Asia/London/NY/London Close]
Quarter (QT): [Q1/Q2/Q3/Q4 Daye]
Session Anchor: [01/05/09/13/17/21 NY]
HTF DOL: [...]
Direction Liquidity: [IRL→ERL / ERL→IRL / Liq→Liq / Imb→Liq / Liq→Imb]
Active Model: [MMBM/MMSM/Neutral]
Delivery State: [...]
Session Narrative: [...]
Judas/Manipulation Status: [...]
SSMT XAU-XAG: [Valid/Invalid/Waiting]
Expansion Quality: [...]
Execution Status: [No Trade / Waiting Confirmation / Valid Setup]
Invalidation: [...]
Target Liquidity: [...]
```

-----

## 9. Product Scope

### In Scope

- XAUUSD analysis
- XAGUSD SSMT confirmation
- Shadow-style narrative interpretation
- quarterly delivery timing
- IRL/ERL/DOL mapping
- MMXM buy/sell model recognition
- Judas Swing and 09 AM Model context
- Telegram alert narrative
- dashboard monitoring
- journal and review
- backtest for delivery concepts

### Out of Scope

- auto-entry tanpa persetujuan trader
- martingale/grid
- indikator retail generik
- sinyal buy/sell tanpa narrative
- copy trading
- financial advice otomatis tanpa risk control

-----

## 10. System Architecture

Architecture tetap sederhana, tetapi semua komponen harus mendukung narrative delivery.

```text
Market Data Source
(TradingView Alert / MT5 / Broker API)
↓
Data Normalizer
↓
Shadow Delivery Interpreter
(DOL + IRL/ERL + Quarter + Session + MMXM + SSMT)
↓
AI Narrative Layer
(GPT / Claude)
↓
Output Layer
(Telegram Bot + Dashboard + Journal)
```

### Backend

- Python FastAPI
- Scheduler untuk session dan quarter timing
- Market data adapter untuk XAUUSD dan XAGUSD
- Database PostgreSQL / Supabase

### Frontend

- Dashboard web Next.js
- TradingView embed atau lightweight chart
- Telegram bot sebagai output cepat

### AI Layer

- GPT/Claude untuk narrative synthesis
- prompt system khusus Shadow Delivery Reasoning
- output harus terstruktur dan konsisten

-----

## 11. Database Entities

### market_snapshots

- id
- symbol
- timeframe
- open
- high
- low
- close
- volume
- timestamp

### liquidity_levels

- id
- symbol
- timeframe
- type: BSL/SSL/IRL/ERL/DOL/previous_high/previous_low
- price
- source_candle
- status: active/taken/invalidated

### delivery_states

- id
- symbol
- timeframe_layer
- quarter
- session
- state
- narrative
- confidence_score
- created_at

### ssmt_events

- id
- primary_symbol: XAUUSD
- confirmation_symbol: XAGUSD
- cic_status
- quarter_sequence_valid
- poi_touched
- xau_relative_state: relative_strength / relative_weakness / neutral
- confirmation_pair_state: confirm / diverge / unclear
- trade_asset: XAUUSD
- liquidity_context
- status

### narratives

- id
- active_dol
- dol_status: active / weakening / shift_pending / shift_confirmed / invalidated
- model
- narrative_text
- continuation_status
- invalidation_level
- invalidation_condition
- target_liquidity
- next_decision_if_invalidated
- created_at

### alerts

- id
- event_type
- symbol
- message
- severity
- sent_to_telegram
- created_at

### trade_journal

- id
- setup_context
- entry_reason
- execution_confirmation
- risk
- result
- mistake_review
- narrative_review

-----

## 12. MVP Requirements

MVP tidak perlu langsung sempurna. MVP harus bisa:

1. Ambil data XAUUSD dan XAGUSD.
1. Tandai previous high/low daily, weekly, session.
1. Tentukan BSL/SSL dasar.
1. Deteksi sweep liquidity.
1. Deteksi quarter aktif berdasarkan NY time.
1. Deteksi SSMT sederhana XAU/XAG berdasarkan swing sequence.
1. Kirim narrative Telegram dengan format Shadow Delivery Snapshot.
1. Simpan alert dan narrative ke database.

MVP belum wajib auto-detect semua FVG/MSS/Breaker. Itu masuk fase berikutnya karena confirmation tools tidak boleh menjadi core system.

-----

## 13. Development Phases

### Phase 1 — Shadow Narrative MVP

- Telegram bot
- data input manual/webhook
- quarter time parser
- basic DOL mapping
- AI narrative output

### Phase 2 — Liquidity and IRL/ERL Mapper

- previous high/low detector
- BSL/SSL
- IRL/ERL mapping multi-timeframe
- liquidity status active/taken

### Phase 3 — SSMT XAU/XAG

- crack in correlation detection
- quarter swing sequencing
- relative strength/weakness classification (XAU primary)
- SSMT validity filter

### Phase 4 — MMXM and Judas Model

- MMBM/MMSM recognition
- HRLR/LRLR logic
- OPR range logic
- Judas Swing and 09 AM model detection

### Phase 5 — Delivery Quality and Failure

- delivery tempo
- expansion quality
- continuation/failure engine
- narrative invalidation

### Phase 6 — Dashboard and Journal

- web dashboard
- active narrative board
- journal review
- alert history
- trade mistake tagging

### Phase 7 — Backtest and Refinement

- backtest DOL/IRL/ERL delivery
- backtest SSMT validity
- backtest Judas + quarter timing
- performance review by session and quarter

-----

## 14. Non-Functional Requirements

- Latency Telegram output maksimal 5 detik setelah event diterima.
- AI output harus konsisten formatnya.
- Sistem harus bisa memberi keputusan “No Trade”.
- Semua reasoning harus bisa dilacak ke data/narrative yang dipakai.
- Sistem tidak boleh overconfident ketika DOL belum jelas.
- Sistem wajib membedakan analysis, confirmation, dan execution.

### No Trade Mandatory Triggers

Sistem wajib output “No Trade” dan menghentikan proses execution jika salah satu kondisi berikut terpenuhi:

**SSMT-related:**

- SSMT terbentuk dalam 1 quarter yang sama (swing 1 dan swing 2 di quarter identik)
- SSMT swing loncat quarter (contoh: Q1 → Q3 tanpa Q2)
- Market algorithm tidak mendukung kondisi SSMT yang terbentuk
- SSMT yang terdeteksi sudah ter-invalidasi via Magneto Effect
- Tidak ada liquidity yang sudah diambil sebelum SSMT terbentuk

**DOL-related:**

- DOL aktif belum dapat diidentifikasi dengan jelas
- Terdapat konflik DOL antara dua timeframe tanpa resolusi yang jelas
- Price berada di area “no man’s land” (tengah range tanpa bias jelas)

**Quarter & Session-related:**

- Quarter aktif bertentangan dengan session narrative
- Session inheritance tidak mendukung delivery
- Hari dalam minggu tidak mendukung pembentukan High/Low yang ditargetkan
- Quarter timing conflict antara DOL dan current delivery state

**Delivery Quality-related:**

- Expansion quality terdeteksi sebagai “exhausted” atau “terminal”
- Delivery tempo “compressed” tanpa retracement yang valid
- Narrative status sudah “failed” atau “reversed”
- Displacement yang terjadi bersifat “engineered” tanpa follow-through

**Execution-related:**

- Tidak ada POI (OB/FVG/Breaker) yang valid di execution timeframe
- RR minimum tidak terpenuhi setelah mempertimbangkan SL ke liquidity terdekat
- News high-impact akan rilis dalam window entry (kecuali narrative mendukung news catalyst)
- CISD/MSS belum terkonfirmasi di LTF

**Output No Trade harus menyertakan:**

- alasan spesifik No Trade,
- kondisi apa yang harus berubah agar setup menjadi valid,
- level atau event yang perlu diperhatikan berikutnya.

-----

## 15. Success Metrics

Produk dianggap berhasil jika:

- AI tidak memberi sinyal mentah tanpa narrative.
- AI mampu menjelaskan DOL aktif dan direction liquidity.
- AI mampu membedakan true liquidity dan engineered liquidity.
- AI mampu menolak setup ketika quarter/session tidak sinkron.
- AI mampu memvalidasi SSMT XAU/XAG dengan konteks liquidity.
- Trader merasa lebih cepat memahami narrative market tanpa harus menulis ulang analisis manual.

-----

## 16. Example AI Output

```text
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Session: NY AM
Session Anchor: 09 NY
HTF DOL: H1 External Sellside Liquidity
Direction Liquidity: ERL→IRL sebelum continuation ke SSL
Active Model: MMSM
Delivery State: London manipulation selesai, NY mencari expansion confirmation
Session Narrative: London mengambil buyside liquidity sebagai engineered liquidity sebelum NY repricing bearish.
Judas/Manipulation Status: Valid, sweep London high sudah terjadi.
SSMT XAU-XAG: Waiting. XAU sweep high, XAG belum confirm high. Jika XAG tetap gagal sweep, bearish SSMT valid.
Expansion Quality: Belum valid, tunggu displacement bearish bersih.
Execution Status: No Trade sampai MSS/FVG confirmation muncul.
Invalidation: Reclaim di atas high sweep dan hold.
Target Liquidity: Asia low / H1 SSL.
```

-----

## 17. Final Product Definition

Imadztrade’s bukan signal bot dan bukan indikator buy/sell. Produk ini adalah:

> **Shadow-style Algorithmic Delivery Interpretation Framework** untuk membantu trader XAUUSD membaca DOL, IRL/ERL, quarter delivery, MMXM, Judas Swing, SSMT XAU/XAG, dan narrative continuation secara sistematis.

Sistem harus membantu trader menjawab:

1. Market sedang deliver ke mana?
1. Liquidity mana yang benar-benar objective?
1. Apakah move sekarang manipulation, expansion, repricing, atau exhaustion?
1. Apakah quarter dan session mendukung continuation?
1. Apakah SSMT XAU/XAG valid setelah liquidity diambil?
1. Kapan harus entry, dan kapan harus no-trade?

-----

## 18. Use Cases — Concrete Implementation Examples

Use case ini berfungsi sebagai **guardrail implementasi** agar developer dan AI coding agent tidak salah tafsir dalam menerjemahkan functional requirement ke dalam logic sistem. Setiap use case menggambarkan kondisi market nyata, reasoning chain yang harus dijalankan, expected output, dan kondisi yang membedakannya dari false positive.

-----

### Use Case 1 — ERL Taken → IRL Rebalance → ERL Target

**FR yang di-cover:** FR-01, FR-02, FR-10

**Kondisi market:**
XAU Daily candle minggu lalu close di bawah Previous Weekly Low. Minggu ini price mulai bergerak naik dari area tersebut. Di H4, terbentuk swing low baru yang tidak ditembus. Di H1, price mulai membentuk higher low.

**Input sistem:**

- Daily: Previous Weekly Low sudah diambil (status: taken)
- H4: Swing low terbentuk, price mulai naik
- H1: IRL terdeteksi di area swing low H4
- ERL terdeteksi di Previous Weekly High

**Reasoning chain yang harus dijalankan:**

1. Sistem identifikasi bahwa Previous Weekly Low sudah diambil → ini adalah liquidity sweep event
1. Sistem tentukan DOL aktif: karena SSL sudah diambil, DOL bergeser ke BSL atas (Previous Weekly High)
1. Sistem baca state sebagai: ERL sudah diambil di bawah, sekarang delivery menuju IRL dulu sebelum lanjut ke ERL atas
1. Sistem turunkan narrative ke H4: apakah H4 mendukung IRL to ERL?
1. Sistem turunkan ke H1: apakah ada imbalance atau OB yang mendukung sebagai POI?
1. Sistem belum boleh output entry — hanya output narrative delivery state

**Expected output:**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
HTF DOL: Previous Weekly High (BSL)
Direction Liquidity: ERL→IRL→ERL
  (ERL bawah/SSL sudah diambil → rebalance ke IRL → target ERL atas/BSL)
Active Model: MMBM kandidat
Delivery State: Post-sweep expansion, delivery aktif ke atas
IRL Level: [harga swing low H4]
ERL Target: [harga Previous Weekly High]
Execution Status: No Trade — tunggu POI confirmation di H1/M15
Invalidation: Break dan close di bawah swing low H4
```

**Yang membedakan dari false positive:**

- Sistem tidak boleh langsung output bullish hanya karena price naik setelah sweep
- Sistem harus membedakan dua tipe sweep SSL: (a) **wick sweep valid** — candle menyentuh level lalu *close kembali di atas* = Turtle Soup / liquidity raid, sweep dianggap selesai dan narrative bisa bergeser; (b) **true breakdown** — candle close dan hold di bawah level = bukan reversal, ini ekspansi bearish berlanjut. Wick sweep BISA menjadi konfirmasi liquidity taken yang valid selama candle close-nya kembali di atas level dan ada displacement follow-through ke arah berlawanan.
- Sistem harus cek apakah H4 mendukung narrative yang sama, bukan hanya Daily

**Edge case:**
Jika H4 masih menunjukkan bearish structure sementara Daily sudah bullish, sistem harus output “conflict resolution needed” dan tidak boleh memberi bias sampai konflik terselesaikan.

-----

### Use Case 2 — Judas Swing + 09 AM Model

**FR yang di-cover:** FR-03, FR-04, FR-05, FR-03A

**Kondisi market:**
Asia session membentuk range antara 4,700 dan 4,730. London session membuka naik dan sweep Asia High di 4,730. Jam 09:00 NY, price masih di atas Asia High. XAG pada saat yang sama tidak ikut sweep high-nya — XAG masih di bawah Asia High XAG.

**Input sistem:**

- Asia range: Low 4,700 / High 4,730
- London: sweep Asia High 4,730
- XAG: gagal confirm sweep high
- Quarter aktif: 09 NY
- Session aktif: NY AM

**Reasoning chain yang harus dijalankan:**

1. Sistem deteksi bahwa Asia High sudah disweep oleh London → ini adalah potential Judas / engineered liquidity
1. Sistem cek: apakah XAG ikut confirm sweep high? → Tidak → CIC terbentuk
1. Sistem evaluasi Judas validity:
- Terjadi di area waktu yang relevan (London / 09 NY)? → Ya
- Menyapu liquidity tertentu (Asia High)? → Ya
- Gagal continue ke atas? → Perlu dikonfirmasi dengan displacement bearish
- Sinkron dengan DOL? → Perlu dicek DOL aktif
1. Sistem output: manipulation flag aktif, tunggu displacement bearish sebagai konfirmasi
1. Sistem belum boleh output sell — hanya tandai sebagai potential Judas

**Expected output:**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Session: NY AM
Session Anchor: 09 NY
HTF DOL: [sesuai HTF context]
Judas/Manipulation Status: POTENTIAL — Asia High swept oleh London,
  XAG gagal confirm. Belum valid sampai ada displacement bearish bersih.
SSMT XAU-XAG: Waiting — XAU sweep high, XAG tidak. CIC terbentuk
  tapi belum ada quarter sequence confirmation.
Expansion Quality: Belum valid — tidak ada displacement bearish
Execution Status: No Trade — tunggu MSS/displacement bearish di bawah
  Asia High sebagai konfirmasi Judas valid
Invalidation: Reclaim dan close di atas sweep high + hold
```

**Yang membedakan dari false positive:**

- Sweep Asia High saja tidak cukup untuk disebut Judas — harus ada kegagalan continue
- XAG harus benar-benar gagal confirm, bukan hanya tertinggal beberapa pips
- Displacement bearish harus bersih, bukan overlap candle biasa

**Edge case:**
Jika setelah sweep Asia High price langsung displacement bearish tanpa retest, sistem harus tetap menunggu POI sebelum output entry. Aggressive displacement tanpa retest diklasifikasikan sebagai “compressed delivery” dan masuk no-trade sampai ada retrace ke OB/FVG.

-----

### Use Case 3 — SSMT XAU/XAG Bearish

**FR yang di-cover:** FR-09, FR-09A, FR-09B, FR-03A

**Kondisi market:**
H4 XAU membentuk swing high baru di Q2 (05 NY) di area 4,850 — ini mengambil Buyside liquidity HTF. H4 XAG pada Q3 (09 NY) membentuk swing high yang lebih rendah dari swing high sebelumnya. XAU di Q3 membentuk swing high yang lebih rendah juga. Dua swing ini berada di quarter berbeda dan berurutan (Q2 → Q3).

**Input sistem:**

- XAU swing high 1: 4,850 di Q2 (05 NY)
- XAU swing high 2: 4,830 di Q3 (09 NY) → Lower High
- XAG swing high 1: 32.50 di Q2
- XAG swing high 2: 32.80 di Q3 → Higher High
- Buyside liquidity HTF sudah diambil sebelum swing high 1
- Quarter sequence: Q2 → Q3 (berurutan, valid)

**Reasoning chain yang harus dijalankan:**

1. Sistem cek apakah liquidity sudah diambil sebelum SSMT → Ya, BSL HTF sudah diambil di 4,850
1. Sistem cek CIC: XAU Lower High + XAG Higher High → divergence terkonfirmasi
1. Sistem cek quarter sequence: Swing 1 di Q2, Swing 2 di Q3 → berurutan, tidak loncat → VALID
1. Sistem baca relative strength/weakness: XAU Lower High sementara XAG Higher High → XAU menunjukkan relative weakness → bias bearish XAU
1. Sistem output SSMT bearish valid, rekomendasikan trade di XAU (primary instrument)
1. Sistem cek apakah ada POI untuk entry: OB/FVG di bawah swing high XAU
1. Sistem belum boleh output sell langsung — harus ada execution confirmation

**Expected output:**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Session Anchor: 09 NY
HTF DOL: SSL / IRL bawah [level]
SSMT XAU-XAG: VALID BEARISH
  XAU: Lower High (4,850 → 4,830)
  XAG: Higher High (32.50 → 32.80)
  Quarter sequence: Q2 → Q3 (valid, berurutan)
  Liquidity context: BSL 4,850 sudah diambil sebelum SSMT
  Relative read: XAU relative weakness (XAU Lower High, XAG Higher High)
  Trade Asset: SHORT XAU (primary instrument; XAG hanya confirmation pair)
Active Model: MMSM kandidat
Delivery State: Post-BSL-sweep, bearish asynchronous delivery
Execution Status: Waiting — perlu MSS bearish dan FVG/OB konfirmasi
  di bawah 4,830 sebelum entry valid
Invalidation: XAU buat Higher High baru di atas 4,850
Target Liquidity: SSL / IRL [level bawah]
```

**Yang membedakan dari false positive:**

- Divergence biasa tanpa liquidity context bukan SSMT
- Quarter yang sama (misal keduanya di Q2) bukan SSMT meski ada divergence
- Quarter loncat (Q2 → Q4) bukan SSMT meski ada divergence
- Sistem wajib reject SSMT jika salah satu kondisi di atas terpenuhi

**Edge case — Magneto Effect:**
Jika setelah SSMT bearish terbentuk, price justru naik dan menembus 4,850 (swing high 1), maka:

1. Sistem harus deteksi bahwa level SSMT sudah ditembus
1. Status SSMT diupdate: `magneto_invalidated`
1. Level 4,850 kini menjadi liquidity baru (BSL baru)
1. Sistem output: “SSMT bearish sebelumnya ter-invalidasi via Magneto Effect. Level 4,850 kini adalah BSL aktif.”
1. Bias direset — sistem harus mulai baca ulang dari DOL

-----

### Use Case 4 — OHLC/OLHC Daily Candle Builder

**FR yang di-cover:** FR-06, FR-06A, FR-03, FR-04

**Kondisi market:**
Hari ini Rabu. Daily candle hari ini open di 4,700. London session membawa price naik ke 4,750 (potensi High of Day). Saat ini jam 09:00 NY, price mulai turun dari 4,750.

**Input sistem:**

- Daily open: 4,700
- Current High: 4,750 (terbentuk di London session)
- Current price: 4,735 (mulai turun)
- Hari: Rabu
- HTF context: Daily sedang dalam narrative bearish (ERL sudah diambil, delivery ke IRL)

**Reasoning chain yang harus dijalankan:**

1. Sistem tentukan candle type: karena HTF bearish, Daily candle hari ini kemungkinan OHLC
1. Sistem baca posisi delivery: Open (4,700) → High sudah terbentuk (4,750 di London) → sekarang fase High → Low
1. Sistem evaluasi timing: Rabu = mid week, valid untuk pembentukan Low of Day yang mendukung Low of Week
1. Sistem turunkan ke H1: apakah ada struktur yang mendukung delivery ke bawah dari 4,750?
1. Sistem cek apakah 4,750 adalah true High atau masih bisa sweep lebih tinggi
1. Sistem output narrative candle builder tanpa langsung bilang sell

**Expected output:**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Session: NY AM
Session Anchor: 09 NY
HTF DOL: Daily IRL bawah [level]
Direction Liquidity: ERL→IRL (Daily OHLC dalam progress)
OHLC Builder Status:
  Daily candle type: OHLC (bearish)
  Open: 4,700
  High: 4,750 (terbentuk London session — kandidat High of Day)
  Current phase: High → Low delivery
  Low target: [IRL level / SSL H1]
  Close projection: di bawah open jika narrative bearish terkonfirmasi
Day-of-Week: Rabu — valid untuk Low of Day formation menuju Low of Week
Session Narrative: London membentuk High sebagai manipulation leg,
  NY diharapkan deliver ke bawah menuju SSL/IRL
Execution Status: Waiting — perlu displacement bearish H1 dari area 4,750
Invalidation: Price kembali ke atas 4,750 dan hold
```

**Yang membedakan dari false positive:**

- High of Day bukan otomatis terbentuk di London — harus dikonfirmasi dengan gagalnya price naik lebih tinggi saat NY open
- Rabu valid untuk Low formation tapi bukan jaminan — harus sinkron dengan HTF narrative
- Sistem tidak boleh output sell hanya karena price turun dari High London tanpa displacement konfirmasi

**Edge case:**
Jika hari ini Jumat dan HTF masih belum mencapai Low of Week, sistem harus output timing conflict: “Low of Week belum terbentuk tapi hari sudah Jumat — probabilitas rendah, higher risk untuk Low formation. Pertimbangkan No Trade atau sizing sangat kecil.”

-----

### Use Case 5 — MMXM Phase Recognition

**FR yang di-cover:** FR-07, FR-01, FR-10

**Kondisi market:**
H4 XAU dalam beberapa minggu terakhir menunjukkan struktur: price turun dari 4,900 ke 4,600 (sell model), lalu dari 4,600 price mulai naik. Saat ini price di 4,720. Fibonacci quadrant dari swing low 4,600 ke swing high 4,900 menempatkan current price di sekitar 0.40.

**Input sistem:**

- Swing High (terminus sell model): 4,900
- Swing Low (SMR point): 4,600
- Current price: 4,720
- Fib position: (4,720 - 4,600) / (4,900 - 4,600) = 0.40

**Reasoning chain yang harus dijalankan:**

1. Sistem tentukan model aktif: dari 4,900 turun ke 4,600 = Sell Model selesai
1. Sistem identifikasi titik terminus: 4,600 = SMR (Smart Money Reversal point)
1. Sistem hitung fib position: 0.40 → masuk fase KOD (0.25–0.50)
1. Sistem baca implikasi fase KOD: area ini adalah zona konsolidasi setelah SMR, potensi Last TS to DOL (turtle soup terakhir sebelum delivery ke atas)
1. Sistem output fase MMXM aktif dan implikasinya
1. Sistem tidak langsung output buy — hanya identifikasi fase dan area probabilitas tinggi

**Expected output:**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Active Model: MMBM (Buy Model aktif setelah Sell Model selesai di 4,600)
MMXM Phase:
  Terminus Sell Model: 4,600 (SMR)
  Swing High reference: 4,900
  Current Fib: 0.40 → Phase KOD
  KOD Implication: Zona konsolidasi / potensi Last TS to DOL
  High probability area: OB/FVG di sekitar 0.25–0.50 fib (4,675–4,750)
  Low risk buy zone: 0.75 fib area (4,825) jika delivery berlanjut
  Final target: 1.0 SMR / liquidity di atas 4,900
Delivery State: Re-accumulation dalam Buy Model
Execution Status: No Trade langsung — identifikasi POI di fib 0.25–0.50
  untuk entry confirmation
Invalidation: Break dan close di bawah terminus 4,600
```

**Yang membedakan dari false positive:**

- Sistem tidak boleh langsung label Buy Model hanya karena price naik
- SMR harus terbentuk dengan konfirmasi displacement bullish dari terminus
- Fib position harus dihitung dari swing yang relevan, bukan swing sembarang

**Edge case:**
Jika price berada di fib > 0.75 tapi belum ada konfirmasi expansion, sistem harus output “low risk area tapi belum ada trigger — tunggu retrace ke OB/FVG sebelum entry.”

-----

### Use Case 6 — News sebagai Delivery Catalyst

**FR yang di-cover:** FR-13, FR-03A, FR-05

**Kondisi market:**
Minggu ini adalah Minggu ke-2 bulan berjalan. Rabu jam 08:30 NY ada rilis CPI. HTF narrative bearish — price masih di atas IRL dan belum delivery ke bawah. Pre-news, London session membawa price naik sedikit dari area konsolidasi.

**Input sistem:**

- News event: CPI Rabu 08:30 NY
- Weekly context: Minggu ke-2 (CPI week)
- HTF narrative: bearish, delivery ke IRL bawah belum selesai
- Pre-news movement: London sedikit naik (potensi accumulation)

**Reasoning chain yang harus dijalankan:**

1. Sistem identifikasi news sebagai delivery catalyst, bukan sinyal random
1. Sistem baca weekly context: Minggu ke-2 = CPI week → historically potential manipulation pre-news
1. Sistem baca pre-news movement: London naik sedikit → ini bisa jadi pre-news liquidity engineering (BSL build-up sebelum reversal)
1. Sistem evaluasi: apakah HTF narrative mendukung bearish catalyst dari CPI?
1. Sistem output: news catalyst alignment dengan narrative, tapi no entry sebelum post-news confirmation
1. Sistem set alert untuk post-news: jika setelah CPI price displacement bearish → konfirmasi narrative

**Expected output:**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Session: London / Pre-NY
Session Anchor: 05 NY (pre-news)
HTF DOL: IRL bawah [level]
News Catalyst: CPI Rabu 08:30 NY
  Weekly context: Minggu ke-2 — CPI week
  Alignment dengan narrative: BEARISH — HTF masih delivery ke IRL bawah
  Pre-news movement: Potential liquidity engineering (BSL build pre-CPI)
  Post-news expectation: Displacement bearish jika CPI sesuai/lebih tinggi
Delivery State: Pre-news accumulation / engineered liquidity build
Judas Risk: Tinggi — London naik bisa jadi Judas sebelum CPI bearish
Execution Status: No Trade sebelum CPI rilis.
  Setelah CPI: valid setup jika ada displacement bearish + FVG/OB konfirmasi
Invalidation: Post-CPI price naik dan reclaim area di atas pre-news high
```

**Yang membedakan dari false positive:**

- Sistem tidak boleh entry sebelum news kecuali narrative sangat jelas dan timing mendukung
- Pre-news movement naik tidak langsung berarti bullish — bisa jadi liquidity engineering
- Post-news harus ada displacement bersih, bukan hanya spike volatilitas tanpa arah

**Edge case:**
Jika CPI rilis tapi tidak ada displacement yang jelas (candle overlap, tidak ada arah), sistem harus output “Post-news delivery inconclusive — No Trade. Tunggu quarter berikutnya untuk clarity.”

-----

### Use Case 7 — OPR (Order Pairing Ranges)

**FR yang di-cover:** FR-01, FR-08, FR-10

**Kondisi market:**
H4 XAU membentuk range selama 3 hari antara 4,680 dan 4,760. Range ini terbentuk setelah sell-off besar dari 4,900. Hari ini price menyentuh dan menembus bawah range di 4,680 (Range Low diambil).

**Input sistem:**

- Range High: 4,760
- Range Low: 4,680
- Current price: 4,672 (di bawah Range Low)
- Context: Range terbentuk post sell-off besar

**Reasoning chain yang harus dijalankan:**

1. Sistem identifikasi range sebagai OPR (Order Pairing Ranges)
1. Sistem deteksi bahwa Range Low (4,680) sudah diambil
1. Sistem evaluasi: sweep Range Low = HRLR atau true breakdown?
1. Sistem cek: apakah ada displacement bearish setelah sweep, atau price langsung bounce?
1. Jika bounce: potensi delivery ke Range High 4,760 (OPR logic — sisi berlawanan)
1. Jika displacement bearish berlanjut: bukan OPR, ini true breakdown menuju target lebih bawah
1. Sistem output sesuai kondisi yang terjadi

**Expected output (scenario: price bounce setelah sweep):**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
HTF DOL: Range High 4,760 (OPR target)
OPR Status: ACTIVE
  Range High: 4,760
  Range Low: 4,680 (TAKEN)
  Sweep type: HRLR — Range Low diambil sebagai manipulation
  Post-sweep action: Bounce terdeteksi → OPR delivery ke atas valid
Direction Liquidity: IRL→ERL dalam konteks OPR
  (Range Low = IRL, Range High = ERL)
Delivery State: Post-HRLR, potensi delivery ke Range High
LRLR Target: 4,760 (Range High)
Execution Status: Waiting — perlu konfirmasi displacement bullish
  dari area sweep (4,672–4,680)
Invalidation: Close dan hold di bawah 4,672 tanpa bounce
```

**Yang membedakan dari false positive:**

- Sweep Range Low saja tidak cukup untuk trigger OPR bullish
- Harus ada kegagalan continue ke bawah setelah sweep
- Bounce harus disertai displacement bullish, bukan hanya wick

**Edge case:**
Jika setelah sweep Range Low, price terus turun dengan displacement bearish, sistem harus update: “OPR invalidated — ini true breakdown. DOL diupdate ke SSL di bawah range. No Trade untuk long.”

-----

### Use Case 8 — Narrative Failure dan Invalidation

**FR yang di-cover:** FR-12, FR-10, FR-01

**Kondisi market:**
Sistem sebelumnya output narrative bullish: DOL = BSL di 4,850, IRL to ERL delivery aktif, SSMT bullish valid. Tapi kemudian price turun dan menembus swing low yang seharusnya jadi batas invalidasi di 4,620.

**Input sistem:**

- Active narrative sebelumnya: bullish, DOL 4,850
- Invalidation level yang sudah di-set: 4,620
- Current price: 4,608 (di bawah invalidation level)
- Volume/displacement: displacement bearish bersih

**Reasoning chain yang harus dijalankan:**

1. Sistem deteksi bahwa price sudah menembus invalidation level 4,620
1. Sistem update narrative status: `active → failed`
1. Sistem batalkan semua output sebelumnya yang bergantung pada narrative bullish ini
1. Sistem identifikasi: apakah ini sweep (HRLR) atau true bearish expansion?
1. Jika displacement bearish bersih → narrative bullish gagal total, mulai baca ulang dari DOL
1. Sistem output narrative failure alert dan reset DOL identification

**Expected output:**

```
⚠️ NARRATIVE FAILURE ALERT
Pair: XAUUSD
Previous Narrative: Bullish — IRL to ERL delivery menuju 4,850
Invalidation Level: 4,620 (BREACHED)
Current Price: 4,608
Displacement: Bearish bersih — bukan sweep

Narrative Status: FAILED
Action: Reset DOL identification
  - BSL 4,850 bukan lagi primary DOL
  - Price sekarang deliver ke bawah
  - SSL baru perlu diidentifikasi

Previous SSMT: Invalidated — narrative yang mendasari sudah gagal
Previous execution setup: CANCELLED

New DOL Candidate: SSL di bawah 4,620 [perlu identifikasi level]
Next Step: Mulai top-down analysis baru dari HTF
Execution Status: No Trade sampai DOL baru terkonfirmasi
```

**Yang membedakan dari false positive:**

- Wick di bawah invalidation level tanpa close tidak otomatis trigger narrative failure
- Sistem harus cek apakah ini sweep (harga kembali) atau true break (close dan hold di bawah)
- Narrative failure harus menyebabkan reset penuh, bukan hanya modifikasi target

**Edge case:**
Jika price breach invalidation level tapi langsung bounce dan close di atas, sistem harus output: “Potential sweep of invalidation level — narrative belum gagal tapi dalam status ‘weakening’. Monitor quarter berikutnya.”

-----

### Use Case 9 — No Trade karena Quarter Conflict

**FR yang di-cover:** FR-03, FR-03A, NFR No Trade Triggers

**Kondisi market:**
HTF narrative bullish valid. DOL = BSL 4,850. Saat ini jam 17:00 NY (Session Anchor 17 NY = London Close). Trader ingin entry buy di area OB 4,710.

**Input sistem:**

- HTF narrative: bullish
- DOL: 4,850
- Session Anchor aktif: 17 NY
- Setup: OB bullish di 4,710
- Session aktif: London Close

**Reasoning chain yang harus dijalankan:**

1. Sistem validasi semua kondisi entry
1. Sistem cek session timing: 17 NY = London Close anchor
1. London Close secara historis adalah: continuation failure atau reversal delivery, bukan expansion
1. Sistem evaluasi: apakah ini waktu yang tepat untuk entry buy?
1. Quarter 17 NY tidak mendukung expansion bullish → timing conflict
1. Sistem output No Trade karena quarter tidak sinkron dengan target delivery

**Expected output:**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
Session Anchor: 17 NY (London Close)
HTF Narrative: Bullish valid
Setup: OB bullish 4,710 terdeteksi
Quarter Assessment: CONFLICT
  17 NY = London Close anchor
  London Close historically: continuation failure / reversal delivery
  Bukan zona expansion yang reliable untuk buy entry
No Trade Reason: Quarter timing tidak sinkron dengan bullish expansion target
  Narrative valid, setup valid, TAPI timing tidak mendukung
Kondisi agar valid: Tunggu Session Anchor 21 NY (Asia open) atau 01 NY
  sebagai re-entry window dengan konfirmasi ulang
Next window: 21 NY atau 01 NY besok
Execution Status: NO TRADE — quarter conflict
```

**Yang membedakan dari false positive:**

- Ini bukan berarti setup salah — narrative dan setup tetap valid
- Hanya timing yang tidak mendukung
- Sistem harus output “setup valid tapi timing conflict” bukan “setup invalid”

-----

### Use Case 10 — HRLR/LRLR Detection

**FR yang di-cover:** FR-08, FR-01, FR-10

**Kondisi market:**
H1 XAU menunjukkan struktur lower highs selama 5 candle terakhir — ini membentuk trendline liquidity (LRLR). Price saat ini mendekati trendline tersebut dari bawah. Di atas trendline ada swing high lama yang signifikan (strong swing point).

**Input sistem:**

- LRLR: trendline dari 5 swing high yang menurun
- Strong swing point di atas: 4,780
- Current price: 4,752 (mendekati trendline LRLR)
- HTF narrative: bearish

**Reasoning chain yang harus dijalankan:**

1. Sistem identifikasi LRLR: penumpukan liquidity dari lower highs yang menurun
1. Sistem identifikasi strong swing point di 4,780 sebagai HRLR target potensial
1. Sistem evaluasi: apakah price akan sweep LRLR dulu sebelum naik ke HRLR?
1. Sistem baca HTF narrative: bearish → LRLR adalah target manipulasi sebelum bearish continuation
1. Sistem output: jika LRLR diambil, monitor apakah price lanjut ke HRLR (4,780) atau langsung reversal
1. Entry bearish ideal: setelah HRLR (4,780) diambil, bukan setelah LRLR

**Expected output:**

```
MARKET DELIVERY SNAPSHOT
Pair: XAUUSD
HTF DOL: SSL bawah [level] (bearish narrative)
HRLR/LRLR Status:
  LRLR Active: Trendline dari 5 lower highs (sekitar 4,752–4,755)
  HRLR Target: Strong swing point 4,780
  Current price: Mendekati LRLR dari bawah
Delivery Assessment:
  Potensi: Price sweep LRLR → lanjut ke HRLR 4,780 → reversal bearish
  Urutan yang diharapkan: LRLR taken → HRLR taken → bearish expansion
LRLR Interpretation: Manipulation target sebelum bearish delivery
Post-HRLR Expectation: Reversal bearish menuju SSL/IRL bawah
Execution Status: No Trade sekarang.
  Entry bearish valid setelah HRLR 4,780 diambil + displacement bearish konfirmasi
Invalidation: Price hold di atas 4,780 dan close dengan bullish displacement
```

**Yang membedakan dari false positive:**

- LRLR bukan target buy — ini adalah liquidity yang akan disweep sebagai manipulasi
- Setelah LRLR diambil, sistem harus tunggu HRLR untuk konfirmasi manipulation complete
- Entry bearish hanya valid setelah HRLR diambil dan ada displacement reversal

-----

### Catatan Implementasi Use Cases

Developer dan AI coding agent wajib memperhatikan:

1. **Tidak ada use case yang langsung output buy/sell** — semua output adalah narrative dan execution status
1. **Setiap use case memiliki “waiting state”** sebelum execution confirmation muncul
1. **No Trade adalah output yang valid** — sistem yang baik lebih sering output No Trade daripada setup
1. **Edge case harus di-handle** — sistem tidak boleh crash atau output kosong ketika kondisi ambigu
1. **Conflict resolution wajib ada** — ketika dua layer timeframe bertentangan, sistem harus resolve bukan ignore
1. **Magneto Effect harus di-track secara aktif** — setiap SSMT event punya lifecycle yang perlu di-monitor
1. **Narrative failure harus trigger reset penuh** — bukan hanya update target saja

-----

## 19. Glossary

| Istilah | Arti |
|---|---|
| DOL | Draw on Liquidity — liquidity objektif tujuan delivery |
| IRL / ERL | Internal / External Range Liquidity |
| BSL / SSL | Buyside / Sellside Liquidity |
| POI | Point of Interest — area reaksi harga (OB/FVG/Breaker) |
| OB | Order Block |
| FVG / IFVG | Fair Value Gap / Inversion FVG |
| BRK | Breaker |
| MSS | Market Structure Shift |
| CIC | Crack in Correlation — divergensi antar pair berkorelasi (dasar SSMT) |
| CISD / CSD | Change in State of Delivery — shift delivery; konfirmasi entry LTF (materi: "Entry = CISD") |
| SMT / SSMT | Smart Money Technique / Sequential SMT |
| SMR | Smart Money Reverse (istilah materi; umum ditulis "Reversal") — titik terminus/pembalikan MMXM |
| TS | Turtle Soup — sweep liquidity (stop run) |
| KOD | Fase di quadrant 0.25 MMXM Swing Grading; zona "Last TS to DOL" + LRLR (materi tidak mendefinisikan kepanjangan akronim) |
| HRLR / LRLR | High / Low Resistance Liquidity Run |
| MMXM | Market Maker Model |
| MMBM / MMSM | Market Maker Buy / Sell Model |
| OPR | Order Pairing Ranges |
| Magneto Effect | SSMT yang sudah mencapai HTF liquidity objective-nya → jadi liquidity baru, invalid sebagai sinyal reversal |
| Quarter (QT) | Quarter Daye (4 per cycle); dasar validasi SSMT |
| Session Anchor | Titik acuan killzone/session (01/05/09/13/17/21 NY); BUKAN quarter QT |
