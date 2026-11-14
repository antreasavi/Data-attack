# Rates tools: how they work and where the data comes from

Analysis date: 13 Nov 2026. Both tools were opened statically. The exe was unpacked, **not executed** by me. It is already running on this PC, and its live output is quoted below.

- `decompiled/` holds reconstructed pseudo-Python for every module of the exe, plus a cell-by-cell dump of the workbook (`fed_funds_xlsx_cells.txt`). The pseudo-code is rebuilt from bytecode, so it's accurate in logic but not runnable as written.
- `re-tools/` holds the scripts that did the extraction. Re-run them when a new exe version arrives (see the bottom of this file).

---

## Tool 1: `1.11.exe`, the "TickerWidget" (v1.11)

**What it is.** A Python 3.11, PySide6 (Qt) desktop app packed with PyInstaller. It shows a frameless strip that stays on top of other windows:

| Column | Colour | Lines |
|---|---|---|
| FED / BOE / ECB / BOJ | green / red / blue / purple | 3 lines each (below) |
| Stack | white / orange / blue | clock, `VIX 18.38`, `US5Y 2.31` |

The 3 lines in each bank column (live values from today):
```
FED DEC +28.9bps        <- next meeting: post-meeting rate minus today's overnight rate
FED DEC26 +28.9bps      <- last meeting of this calendar year, cumulative
FED +25.0bps BY DEC26   <- first meeting where the cumulative move reaches 25bp ("NOT BY <date>" if never)
```
Hover over a bank column for 0.3 s and a chart appears. It plots the post-meeting rate for the next 6 meetings, with the date and the bp change for each.

**Safety check.** It makes no subprocess, shell, eval or socket calls, and has no licence check or telemetry. Its only network traffic goes to the sources listed below.

### Architecture
```
launcher ─┬─ thread: ois_feed   (every 5 min)  ─┐
          ├─ thread: VIX        (every 10 min) ─┼─> %LOCALAPPDATA%\TickerWidget\data\*.txt / *.json
          ├─ thread: US5Y       (every 10 min) ─┘          (atomic writes)
          └─ Qt GUI (main.py): checks file mtimes every 2 s, clock every 1 s, hover every 100 ms
```
Logs go to `%LOCALAPPDATA%\TickerWidget\logs\app.log`. The JSON files `ois_fed.json`, `ois_boe.json` and the others hold the full meeting path, 24 monthly forwards, and source details for each bank. **They are directly reusable.**

### Core method (`ois_feed.py` + `market_composite.py`)
1. **Eurex OIS curves (main source).** The app scrapes the Eurex OTC Clear settlement-prices page, finds the newest `settlement-prices_YYYYMMDD.csv`, and reads the **daily discount factors** for days 0 to 1100 on four curves:
   - `USD.FEDFUNDS.1D` (ACT/360)
   - `GBP.SONIA.1D` (ACT/365)
   - `EUR.ESTR.1D` (ACT/360)
   - `JPY.TONAR.1D` (ACT/365)

   It rejects a curve that is more than 7 days old, mixes valuation dates, or has gaps.
2. **Forward between two dates:** `(DF(start)/DF(end) − 1) × basis / days × 100`.
   **Base rate:** the 1-day forward on the curve date. Every change is measured against this base.
3. **Meeting periods.** The meeting dates are scraped from each central bank's own site:

   | Bank | Period used |
   |---|---|
   | FED | day after the meeting → day after the next meeting (weekends skipped) |
   | BOE | announcement → next announcement (ICE MPC SONIA convention) |
   | ECB | published reserve maintenance periods |
   | BOJ | next BOJ business day, using the official BOJ holiday list |
4. **BOE and ECB only: composite with ICE.** The app takes delayed last trades from ICE meeting-dated futures. It drops quotes older than 72 h.
   - Weight = `quality × 2^(−age_h / 24)`.
   - Quality is 0.5 for the Eurex curve and 1.0 for an ICE trade, or 0.25 if the trade volume is under 10.
   - The result is a weighted mean, with one vote per source.
   - When ICE is used, the popup reads "ICE/Eurex | mixed quote times".
5. **Diagnostics only (never shown in the ticker):**
   - ECB results checked against Eurex FEMP daily settlements.
   - A checkmyswap.com par-curve status check.

### VIX and "US5Y"
- **VIX:** the yfinance `^VIX` latest close.
- **"US5Y" is really the 5-year *breakeven inflation rate*, not the 5-year yield.** It is computed as Yahoo `^FVX` (5Y nominal yield) minus the Treasury 5Y real (TIPS) yield.

### Code in the exe that isn't used
- `FED/fetch_fed` + `fed_ois.fetch`: a CME-FedWatch-style ZQ path (ZQ via Yahoo, EFFR from the NY Fed). The ZQ arithmetic is the same as the spreadsheet's.
- `BOE/fetch_boe` + `boe_ois.fetch`: the BoE's own OIS forward curve.
- `ratecore` run schedule: 06:30, 11:20, 16:10 and 21:00 London.

None of these are started anymore. Only their FOMC and MPC date scrapers are still used. Leftover `data_boc.txt` and `data_snb.txt` files show an older version also covered the BoC and SNB.

### Sources (exe)
| Data | URL / API | Notes |
|---|---|---|
| OIS discount factors (4 ccy) | eurex.com/ec-en/clear/eurex-otc-clear/settlement-prices → daily CSV | Free. **End of day, T-1** |
| ICE futures (BOE, ECB) | ice.com/marketdata/api/productguide/charting/contract-data?productId=30027 (BOE) / 29802 (ECB) | Delayed last trades, 4-min cache |
| ICE expiry calendars | ice.com/api/productguide/spec/83047279 (BOE) / 83046794 (ECB) /expiry/csv | Daily cache |
| FOMC dates | federalreserve.gov/monetarypolicy/fomccalendars.htm | HTML scrape |
| MPC dates | bankofengland.co.uk/monetary-policy/upcoming-mpc-dates | HTML scrape |
| ECB dates / maintenance periods | ecb.europa.eu …/calendars/mgcgc/… and …/calendars/reserve/… (+ 2 hard-coded press releases) | HTML scrape |
| BOJ dates / holidays | boj.or.jp/en/mopo/mpmsche_minu/ and boj.or.jp/en/about/outline/holi.htm | HTML scrape |
| ECB check | eurex.com/api/v1/overallstatistics/4853044 (FEMP) | Diagnostic only |
| Reference curves | checkmyswap.com/api/curves/all | Diagnostic only |
| VIX, ^FVX | Yahoo via yfinance | Unofficial API |
| 5Y TIPS real yield | home.treasury.gov daily_treasury_real_yield_curve CSV | End of day |
| *(unused)* EFFR | markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json | |
| *(unused)* ZQ | query1.finance.yahoo.com/v8/finance/chart/ZQ{M}{YY}.CBT | |
| *(unused)* BoE curve, Bank Rate, SONIA | BoE latest-yield-curve-data.zip; IADB series IUDBEDR / IUDSOIA | |

### Weak spots (exe)
- **FED and BOJ change only once a day.** The Eurex file is end of day (T-1), so the 5-minute refresh just re-checks whether a new file exists. Only BOE and ECB move during the day, through delayed ICE quotes.
- The Fed number comes from **OIS, not from ZQ**, and the app shows **no probabilities**.
- The base is the overnight rate on the curve date, not today's EFFR fixing.
- Every meeting calendar is scraped from HTML, so it breaks if a site changes its layout. Yahoo is an unofficial API.
- The US5Y label is misleading. The breakeven also mixes a live nominal yield with the previous day's real yield.

---

## Tool 2: `Fed Funds from June.xlsx`

**What it is.** A copy of the CME FedWatch method, built by hand. It covers the FOMC meetings from Jun-26 to Mar-27. It was last saved on 16 Jun 2026, the day before the June meeting.

**Source.** Live prices from **Trading Technologies (TT) through Excel RTD**:
```
B3: =RTD("tt.rtd",,"Inst","CME","ZQM6")      -> TT instrument id
E7: =RTD("tt.rtd",,E$3,"Bid")                -> fields: Bid/Ask/Last/Settle/Open/High/Low/TTQ/qtys...
```
It needs TT running and logged in, with CME market data. Nothing else in the workbook is external.

### Sheet1: market data
- There are 13 CME 30-day Fed Funds (ZQ) contracts, ZQH6 to ZQH7.
- H6, J6 and K6 have expired and show `failedToFindInstrument`, which is harmless.
- Row 27 is the price used: the **mid, (Bid + Ask) / 2**.

### Spread sheet: the model
1. **Implied monthly average rate** = `100 − mid`.
2. **Meeting dates are typed in by hand** (column C): 17 Jun, 29 Jul, 16 Sep, 28 Oct, 9 Dec 2026, 27 Jan and 17 Mar 2027.
3. **Anchor months** (Aug, Nov and Feb have no meeting): the monthly average *is* the rate.
4. **Meeting months:** `avg × N = d × pre + (N − d) × post`, where d = the meeting day.
   - Solved **backward** from the next anchor month for Jun, Jul, Oct and Jan.
   - Solved **forward** from the previous rate for Sep (pre-meeting rate), Dec and Mar.
5. **Number of steps** = `(post − pre) / 0.25`. This is turned into a **binary** split: P(hike) = steps if positive, P(cut) = −steps if negative, hold = the rest. If the result is 1 step or more, the cell shows `ERROR`.
6. **Probability tree** (columns Y:AM): buckets from −7 to +7 steps around the 3.50–3.75% range. Each meeting rolls it forward: `P[j] = P[j]·hold + P[j+1]·cut + P[j−1]·hike`.
7. **AP** = the expected cumulative number of 25bp moves. The chart "% of rate change priced in by month" plots AP (end of month) and an "Avg Implied" (month-average) series.

Snapshot as saved: June 5% hike odds. About 1.1 hikes priced by Mar-27.

### Weak spots (xlsx)
- **Rolling is manual.** The contracts, meeting dates and month labels are all hard-coded.
- **No real EFFR input**, even though a column is headed "EFFR". The starting rate is worked back out of the futures.
- **Only one 25bp step per meeting.** A 50bp move, or anything over 100% of one step, shows `ERROR`.
- **The forward and backward solves disagree.** The Dec post-meeting rate (forward, 3.822) ≠ the Jan pre-meeting rate (backward, 3.819). Because of this, AP and the check column AR drift apart from January (0.932 vs 0.919).
- **The mid can be wide or stale** in thin back months. There is no fallback to Last or Settle.
- **Label typo:** AM3 reads "474 - 500" but should be "525 - 550".

---

## Tool 2, current version: the "Implied rate path" dashboard

*Source: a screenshot the user shared on 13 Nov 2026, taken 6 Nov. Everything below is read off the UI. The code and data feed are not yet confirmed.*

The xlsx has grown into a dark-theme dashboard (it looks like HTML/JS, with a full-screen button). It shows **the cumulative implied Fed move at each FOMC meeting** from Dec-26 to Dec-27. That's 9 meetings ("9 shown"), worked out from 15 ZQ months ("Load 15 months").

| Control | What it does (inferred) |
|---|---|
| Relative / Absolute | Change vs today's rate (bp) / implied rate level |
| bp / % | Right axis in bp. Left axis "Hike %", where **25 bp = 100%** (e.g. 300% = 75 bp) |
| Compare + T−1 day, + Comparison | Overlays an older snapshot (dashed line); more can be added |
| Δ ticks | Shows, under each meeting, the contract's price change vs the comparison. About 0.5 bp per tick |
| Freeze Y | Locks the y-axis scale |
| Meeting months (dropdown) | Plots meeting dates only. Other choices are probably all contract months |
| Bid/Ask Midpoint (dropdown) | Price source. Other choices are probably Last and Settle (the xlsx used the mid) |

Snapshot shown: Latest = 6 Nov 07:38:00 NY, T−1d = 5 Nov 07:23:55 NY.

| | Dec 26 | Jan 27 | Mar 27 | Apr 27 | Jun 27 | Jul 27 | Sep 27 | Oct 27 | Dec 27 |
|---|---|---|---|---|---|---|---|---|---|
| Latest (bp) | +18.x | +23.2 | +32.5 | +36.2 | +42.1 | +43.7 | +45.3 | +45.0 | +43.3 |
| T−1d (bp, read from the chart) | ~21 | ~28 | ~42 | ~49 | ~57 | ~59 | ~61 | ~60 | ~57 |
| Δ ticks | +6 | +8 | +16 | +22 | +30 | +32 | +34 | +33 | +30 |

**What changed from the xlsx (it seems):**
- Rolls forward automatically: the meetings now run to Dec-27.
- Shows cumulative moves above 1 step, so the old `ERROR` cap no longer applies to the path.
- Keeps time-stamped intraday snapshots in NY time, which the xlsx never did.
- Price source is selectable.

**Not visible in this view:**
- The per-meeting hike/hold/cut probabilities and the probability tree from the xlsx.
- What "Relative" is measured from (EFFR? the front ZQ month? the current target range?).

**Small UI issues:**
- At Dec-26 the latest and T−1 labels overlap ("+18.x bp" is unreadable).
- Something red is cut off at the right edge, around y = 280.

**Open questions:**
- Where does it run, and is the source available?
- Is the feed still TT RTD?
- How are snapshots stored?

**Cross-check with the exe:** not possible yet. This screenshot is from 6 Nov, and the exe's data is from 12 Nov (it showed FED Dec +28.9 bp vs an OIS overnight rate of 3.88%). Compare them at the same timestamp once both feed one tool.

---

## Side by side

| | TickerWidget exe | Fed Funds xlsx (original) | Tool 2 dashboard (current) |
|---|---|---|---|
| Banks | FED, BOE, ECB, BOJ | FED only | FED only |
| Instrument | OIS discount curves (+ ICE futures for BOE/ECB) | CME ZQ futures | CME ZQ futures (15 months) |
| Freshness | End of day T-1 (FED/BOJ); delayed intraday (BOE/ECB) | **Real-time** (TT) | **Intraday snapshots** (NY time) |
| History / compare | None (latest only) | None | T−1 and custom comparisons, Δ ticks |
| Meeting dates | Scraped automatically | Typed by hand | Rolls forward (method unknown) |
| Output | Bp priced per meeting, cumulative path, "first 25bp by" | Hike/hold/cut % per meeting, probability tree, chart | Cumulative bp / hike-% path chart |
| Cost / dependency | Free public data | TT licence + CME data | Probably TT + CME data |

They complement each other:
- **The exe** has the plumbing: automatic calendars, free curves, multiple banks and the ticker UI.
- **The dashboard** has real-time Fed pricing, history and comparison.
- **The xlsx** still holds the probability maths.

---

## Re-running the extraction on a new exe version
```bash
py -m venv venv && venv/Scripts/python -m pip install xdis
python -I re-tools/carchive.py <new.exe> out/            # unpack the PyInstaller bundle
python -I re-tools/pyz.py out/PYZ.pyz pyz/               # unpack the bundled modules
venv/Scripts/python -I re-tools/pseudo.py pyz/ois_feed.pyc ois_feed.py   # rebuild readable code, per module
python -I re-tools/dumpxlsx.py <unzipped xlsx dir>       # dump workbook formulas + values
```
