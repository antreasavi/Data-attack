# Auction Watch

Waits for the next Treasury **auction results** PDF on TreasuryDirect
(Auctions → Announcements, Data & Results) and puts it on a **results page you keep
open**. The PDF appears there the moment it is posted, with the headline numbers above it.

By default it watches the **1:00 PM ET** note/bond auctions.

## The link

**http://localhost:8845/** works whenever the watcher is running. The page is served by
the watcher itself, so if nothing is running the browser says it can't connect.

The reliable way to open it is the **Auction Watch** icon on your desktop. Each click:

1. checks whether the watcher is running, and if not starts it **in the background**
   (no window to close by accident),
2. opens the page.

Clicking it again never starts a second copy. If the watcher was killed or the PC
restarted, the next click brings it back in a few seconds.

Set the icon up (or again, if you move this folder):

```bash
powershell -ExecutionPolicy Bypass -File install-shortcuts.ps1
```

Add `-Startup` to also start the watcher silently when you sign in to Windows, so a
bookmarked `http://localhost:8845/` works straight after a reboot. `-Remove` takes both
shortcuts away. **`STOP-auction-watch.cmd`** stops the background watcher; its log is
`data\watch.log`.

Prefer a console window you can watch? Double‑click **`RUN-auction-watch.cmd`** instead.
It runs the same watcher with a visible window, and opens the page too.

On the page, click **Enable sound** once (browsers only allow a page to make noise after a click).

What you see:

- **Before the drop:** a status pill with the countdown to polling, the next auction
  (security, size, close time in ET and your local time), and the most recent
  published result, labelled **PREVIOUS**, so the page is never empty.
- **At the drop** (usually ~1:02 PM ET): the new PDF replaces it, fitted to the width,
  with a strip above it showing high yield, allotted at high, median/low,
  **bid‑to‑cover**, and the indirect / direct / dealer shares. The strip flashes
  green, the page chimes, and the tab title blinks. Click **Got it** or press any key to stop the flashing.
- **Open PDF** / **TreasuryDirect** open the same file in a new tab. After more than one
  result, a menu at the top lets you flip between them.

The page reads the watcher's state twice a second, so the PDF shows up within about a
second of the watcher getting it. If the window is closed, the page says
**Watcher not running** and reconnects by itself when you start it again.

After a drop, it moves on to the next 1:00 PM auction. If none is announced yet, it
re-checks the schedule every 15 minutes, so you can leave it running all week.

## Options

```bash
powershell -ExecutionPolicy Bypass -File watch.ps1 -CloseTime "11:30 AM"   # bill auctions instead
powershell -ExecutionPolicy Bypass -File watch.ps1 -CloseTime any          # every auction
powershell -ExecutionPolicy Bypass -File watch.ps1 -Date 2026-11-09        # only that day
powershell -ExecutionPolicy Bypass -File watch.ps1 -Once                   # stop watching after one drop
powershell -ExecutionPolicy Bypass -File watch.ps1 -IntervalSeconds 1      # poll faster around the drop
powershell -ExecutionPolicy Bypass -File watch.ps1 -OpenPdf                # also open each PDF in your PDF viewer
powershell -ExecutionPolicy Bypass -File watch.ps1 -NoPage                 # no page: just open the PDF + beep
powershell -ExecutionPolicy Bypass -File watch.ps1 -Port 8846              # if 8845 is taken
powershell -ExecutionPolicy Bypass -File watch.ps1 -NoBrowser              # page already open in a tab
```

The same options work on the launcher: `RUN-auction-watch.cmd -CloseTime "11:30 AM"`.

## Try it now

```bash
powershell -ExecutionPolicy Bypass -File watch.ps1 -Demo
```

Opens the page, then about 5 s later drops the most recent published 1:00 PM result onto
it, just like a live drop.

```bash
powershell -ExecutionPolicy Bypass -File watch.ps1 -Replay 2026-10-29
```

Re-runs drop detection against a past auction day. It pretends it doesn't know any file
names and scans like it would live: it skips the morning bill results and picks out the
1:00 PM one by CUSIP.

## How it works

The Announcements, Data & Results page is built from TreasuryDirect's data feed
(`/TA_WS/securities/...`). That feed is used for the **schedule** only. It updates
1–2 minutes *after* the PDF is posted, so it's too slow to catch the drop.

The results PDFs are numbered in release order for each auction date:

```
https://www.treasurydirect.gov/instit/annceresult/press/preanre/<yyyy>/R_<yyyymmdd>_<n>.pdf
```

so on a day with two 11:30 bill auctions, the 1:00 PM result is `R_<date>_3.pdf`.
From one minute before the close, the watcher sends a small HEAD request to the next
unused numbers every 2 s (404 means it isn't posted yet). When one goes live, it downloads
the file and reads the CUSIP from it with `pdftotext` (comes with Git for Windows); if
`pdftotext` is missing, it reads the CUSIP from the matching XML instead. That way a late
bill result can never be mistaken for the one you're waiting for. The data feed is also
checked every 15 s as a backstop.

Once it's confirmed, the watcher writes `data/state.json`. The page (served by the same
window on localhost) picks that up and loads the PDF from `data/`. The summary numbers
come from the matching results XML
(`https://www.treasurydirect.gov/xml/R_<yyyymmdd>_<n>.xml`), posted at the same time.

| File | Job |
|------|-----|
| `install-shortcuts.ps1` | creates the desktop icon (and, with `-Startup`, the sign‑in start) |
| `open.ps1` | what the desktop icon runs: start the watcher in the background if needed, open the page |
| `RUN-auction-watch.cmd` | console launcher (visible window) |
| `STOP-auction-watch.cmd` / `stop.ps1` | stop the watcher, including a background one |
| `watch.ps1` | schedule, polling, download, CUSIP check, `state.json`, and the page server. Only one copy runs per data folder |
| `auction-watch.ico` | the desktop icon |
| `index.html` / `app.js` / `style.css` | the results page |
| `data/` | downloaded PDFs, `state.json`, `watch.log` (git‑ignored) |

## Notes

- The PC has to be awake with the window open. If it sleeps, it picks up again when it wakes.
- Times use US Eastern time, so daylight saving is handled automatically. Your local time is shown alongside.
- During the drop window it makes about one small request every 2 s for a few
  minutes. Outside that window it only reads the schedule every 15–30 minutes.
- If no PDF shows up within 60 minutes of the close (a delayed auction), it gives up
  on that one and moves to the next. Use `-GiveUpMinutes` to change this.
- Bid‑side shares are each bidder class's share of the **competitive** amount awarded.
- The desktop notification shows only when the page's tab is in the background, and only if
  you allowed notifications when you clicked **Enable sound**.
