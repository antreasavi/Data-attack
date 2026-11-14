# Fed STIR scenario tool: spec (v1)

Agreed 14 Nov 2026. Trades **ZQ** (30-day Fed Funds) and **SR3** (3-month SOFR). All market data comes from **Sierra Chart**. TT is not used.

## The question it answers
> "The market prices X for the next FOMC right now. If a speaker moves that to +50, +75 or a cut, where should every ZQ and SR3 contract trade, and which contract hasn't moved yet?"

## Data (all checked 14 Nov)
| Input | Source | Status |
|---|---|---|
| Live bid / ask / last, per contract | Sierra tick files (`.scid`) in `SierraChartInstance_5\Data`, from the **STERS** chartbook (intraday charts) | Readable. Tick-by-tick back to 12 May 2026. Live streaming to be confirmed when Globex opens Sun 6pm ET |
| Settlement (yesterday) | Sierra daily files (`.dly`): their "close" = the 2pm CT settlement | Readable |
| Contracts | ZQ X26–J27 (6), SR3 Z26–M28 (7) | More can be added in Sierra at any time |
| EFFR, SOFR fixings | NY Fed markets API (free, no key) | Same source the TickerWidget uses |
| FOMC dates | federalreserve.gov calendar (scraped, as in the TickerWidget) | |
| Fed speaker schedule | federalreserve.gov calendar for Board members; regional presidents added by hand | |

**Quote age matters.** Sierra only updates bid/ask when a trade prints. SR3 trades every few seconds, but some ZQ months went 30–50 min without a trade on 13 Nov. Every price shows its age, and old quotes are flagged.

## Model
1. **Policy path:** a step function. It starts at today's EFFR, and each FOMC step takes effect the day after the meeting.
2. **ZQ fair price** = 100 − the average daily EFFR over the contract month.
3. **SR3 fair price** = 100 − SOFR compounded daily over the IMM period (third Wednesday to third Wednesday). Fixings already published are locked in for the quarter in progress.
4. **SOFR vs EFFR spread:** fitted from the market.
5. **"Current pricing":** the size of each meeting's step is fitted to the live mid-prices of all ZQ and SR3 contracts at once (least squares, with fresher and more liquid quotes counting more).
6. **Lagging contracts** = how far each contract sits from the fitted curve now, minus how far it sat at last settlement. Subtracting the settlement gap removes each contract's normal, permanent gap from the curve, so a contract is flagged only when it hasn't caught up with today's move.
7. **Tick rules (CME):**
   - ZQ: 0.0025 in the spot month ($10.4175), 0.005 in the others ($20.835).
   - SR3: 0.0025 in the nearest quarter ($6.25), 0.005 in the others ($12.50).

## Scenarios
- **One-click buttons per meeting:** Cut / Hold / +25 / +50 / +75, meaning the total move priced by that meeting.
- **Path-shift switch** (default: whole path):
  - *Whole path:* the change carries through every later meeting.
  - *Pull-forward:* the later path is unchanged, so the end rate stays the same. Later meetings are only lifted or lowered as far as needed to stay consistent with the new level.
  - *Fade:* later meetings move by the change × a decay factor per meeting (adjustable).
- **Output per contract:** current mid, scenario target, **ticks to target** (sorted biggest first), quote age.
- **Speaker ladders:** for each upcoming speaker, a ready-made table of outcomes for the focus meeting (default: the next one), from Cut through +75. It shows each contract's target price and ticks from now.

## Screens
- **Local web page** (full view):
  - rate path chart: now vs settlement
  - scenario buttons and the path-shift switch
  - contract table with ticks to target and lagging flags
  - speaker ladders
- **Always-on-top strip** (compact):
  - per meeting: the bp priced now and the change vs settlement
  - the top lagging contracts
  - the last scenario's best targets

## v1 build order
1. Sierra live reader: tail the tick files, track quote age, read settlements from the daily files.
2. NY Fed and Fed calendar fetchers (cached).
3. Pricing model and fit (ZQ + SR3), checked against settlements.
4. Scenario engine (three path-shift modes) and lagging measure.
5. Web page.
6. Always-on-top strip.
7. Speaker ladders.

## Later (not v1)
- Better live quotes for thin ZQ months: either a small Sierra study that writes the real order book, or ZQ quotes inferred from SR3.
- Probabilities (hike/hold/cut %) as in the original workbook.
- BoE / ECB (SONIA, €STR) using the TickerWidget's work.

## How to run (v1, built 14 Nov 2026)
- **Start:** double-click `rates-tools/Start Fed STIR tool.bat`. It starts the engine (minimised window), opens the web page at http://127.0.0.1:8791/ and starts the always-on-top strip.
- **Strip:** drag with the left mouse button, double-click to open the web page, right-click for the menu.
- **Needs:** Sierra running, with the **STERS** chartbook (instance 5) open as intraday charts. Contracts added to STERS appear in the tool within ~20 s.
- **Check the Sierra files on their own:** `python -I rates-tools/sierra_check.py`.
- **Tests:** from `rates-tools`, run `python -m unittest discover -s tests`.
- **Cache** (NY Fed fixings, FOMC dates, speakers, your added speakers): `%LOCALAPPDATA%\StirTool`.
- **Settings:** data folder, chartbook and port can be changed in `rates-tools/stirtool/config.json`, e.g. `{"port": 8791}`.

Code map (`rates-tools/stirtool/`):

| File | What it does |
|---|---|
| `sierra.py` | live tick reader and settlements |
| `sources.py` | NY Fed, FOMC and speaker downloads |
| `model.py` | pricing and curve fit |
| `scenario.py` | the three path-shift modes, ladders and lag |
| `engine.py` | background loop |
| `server.py` | local web server |
| `static/index.html` | the web page |
| `strip.py` | the always-on-top strip |
