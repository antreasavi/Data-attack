# Auction Watch

Waits for the next Treasury **auction results** PDF on TreasuryDirect
(Auctions → Announcements, Data & Results), downloads it the moment it is
posted, and **opens it**. It also beeps and prints the headline numbers in the window.

By default it watches the **1:00 PM ET** note/bond auctions.

## Run it

Double‑click **`RUN-auction-watch.cmd`** and leave the window open. It will:

1. read TreasuryDirect's auction schedule and show the next 1:00 PM auction
   (security, CUSIP, size, and the time in ET and in your local time),
2. count down, then start polling at **12:59:00 PM ET** every 2 s,
3. as soon as the results PDF appears (usually ~1:02 PM ET), download it to
   `data\`, check the CUSIP inside it is the right auction, and open it in your PDF viewer,
4. print something like:

```
*** RESULTS OUT:  7-Year Note   CUSIP 91282CRV5 ***
  Got it   1:02:19 PM ET  /  17:02:19 local   (00:02:19 after the close)
  High yield    4.894 %   (allotted at high 63.94 %)
  Median / low  4.840 / 4.770
  Bid-to-cover  2.46
  Awarded       indirect 57.8 %   direct 32.8 %   dealers 9.4 %
```

5. then move on and wait for the next 1:00 PM auction. If none is announced yet,
   it re-checks the schedule every 15 minutes, so you can leave it running all week.

## Options

```bash
powershell -ExecutionPolicy Bypass -File watch.ps1 -CloseTime "11:30 AM"   # bill auctions instead
powershell -ExecutionPolicy Bypass -File watch.ps1 -CloseTime any          # every auction
powershell -ExecutionPolicy Bypass -File watch.ps1 -Date 2026-11-09        # only that day
powershell -ExecutionPolicy Bypass -File watch.ps1 -Once                   # stop after one drop
powershell -ExecutionPolicy Bypass -File watch.ps1 -IntervalSeconds 1      # poll faster around the drop
powershell -ExecutionPolicy Bypass -File watch.ps1 -NoOpen -NoSound
```

The same options work on the launcher: `RUN-auction-watch.cmd -CloseTime "11:30 AM"`.

## Try it now

```bash
powershell -ExecutionPolicy Bypass -File watch.ps1 -Demo
```

Downloads and opens the most recent published 1:00 PM result right away.

```bash
powershell -ExecutionPolicy Bypass -File watch.ps1 -Replay 2026-10-29
```

Re-runs drop detection against a past auction day. It pretends it doesn't know
any file names and scans like it would live: it skips the morning bill results
and picks out the 1:00 PM one by CUSIP.

## How it works

The Announcements, Data & Results page is built from TreasuryDirect's data feed
(`/TA_WS/securities/...`). That feed is used for the **schedule** only. It
updates 1–2 minutes *after* the PDF is posted, so it's too slow to catch the drop.

The results PDFs are numbered in release order for each auction date:

```
https://www.treasurydirect.gov/instit/annceresult/press/preanre/<yyyy>/R_<yyyymmdd>_<n>.pdf
```

so on a day with two 11:30 bill auctions, the 1:00 PM result is `R_<date>_3.pdf`.
Around the close, the watcher sends small HEAD requests to the next unused numbers
(404 means it isn't posted yet). When one goes live, it downloads the file and
reads the CUSIP from it with `pdftotext` (comes with Git for Windows); if
`pdftotext` is missing, it reads the CUSIP from the matching XML instead. That way a
late bill result can never be mistaken for the one you're waiting for. The data
feed is also checked every 15 s as a backstop.

The summary numbers come from the matching results XML
(`https://www.treasurydirect.gov/xml/R_<yyyymmdd>_<n>.xml`), posted at the same time.

## Notes

- The PC has to be awake with this window open. If it sleeps, it picks up again when it wakes.
- Times use US Eastern time, so daylight saving is handled automatically. Your local time is shown alongside.
- During the drop window it makes about one small request every 2 s for a few
  minutes. Outside that window it only reads the schedule every 15–30 minutes.
- If no PDF shows up within 60 minutes of the close (a delayed auction), it gives up
  on that one and moves to the next. Use `-GiveUpMinutes` to change this.
- Bid-side shares are each bidder class's share of the **competitive** amount awarded.
