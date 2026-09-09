# Buyback Watch

Polls a TreasuryDirect buyback **Preliminary Announcement** PDF. The moment the
URL goes live it downloads the PDF, pulls out the buyback dollar amount
("Maximum Par Amount to be Redeemed"), and a browser page turns it into a
full‑screen colour flash + desktop notification + sound, with the amount shown huge.

Default target:
`https://www.treasurydirect.gov/instit/annceresult/press/preanre/2026/BBPA_20260910174000.pdf`

## Run it

**Easiest:** in File Explorer, open this folder and double‑click
**`RUN-buyback-watch.cmd`**.

Or from PowerShell in this folder:

```bash
powershell -ExecutionPolicy Bypass -File start.ps1
```

Either way you get **one window**. It serves the alert page *and* polls, opens
`http://localhost:8844/` in your browser, and checks every 20 s. **Keep that one
window open** (closing it or Ctrl+C stops everything). On the page, click
**Enable sound + notifications** once (browsers only allow noise / notifications
after a click). Use **Preview alert** to see what it looks like.

If the page doesn't load, the port is probably taken — run
`start.ps1 -Port 8850` and open `http://localhost:8850/`.

Options:

```bash
powershell -ExecutionPolicy Bypass -File start.ps1 -IntervalSeconds 10
powershell -ExecutionPolicy Bypass -File start.ps1 -Url "https://www.treasurydirect.gov/instit/annceresult/press/preanre/2026/BBPA_XXXXXXXXXXXXXX.pdf"
powershell -ExecutionPolicy Bypass -File start.ps1 -Port 8850
powershell -ExecutionPolicy Bypass -File start.ps1 -NotBefore 2026-09-10 -FanoutDays 3
powershell -ExecutionPolicy Bypass -File start.ps1 -ExactUrlOnly
```

### Which file it actually watches

It always polls the exact `-Url` first. Unless `-ExactUrlOnly` is set it *also*
probes, each cycle:

- the same date **through `-FanoutDays` days later** (default 2), in case the
  operation date slips,
- the other usual close‑time stamps (`174000`, `184000`, `164000`), in case the
  filename time differs,
- the `fiscaldata.treasury.gov` mirror of each name.

It will **never** accept a file dated before the floor date — `-NotBefore`, or
the date in `-Url` if that's not given. That's what stops an already‑published
earlier operation (e.g. the Sept 9 2026 $12.5B one) from triggering a false
alarm when you're waiting on a later one. One full sweep of ~18 names takes ~5 s.

## What pops up

The whole screen floods with a colour keyed to the size of the buyback:

| Amount            | Colour   |
|-------------------|----------|
| under $1B         | blue     |
| $1B – $3B         | green    |
| $3B – $5B         | orange   |
| $5B – $10B        | red      |
| $10B and up       | dark red |

There is **no upper cap** on the amount it can read — a figure like
`$12,500,000,000` is parsed and shown as `$12.5B`.

plus the amount ("$2B" / "$2,000,000,000"), operation type (nominal vs TIPS),
maturity range, operation date, a link to the PDF, and an **Acknowledge** button
that stops the flashing and the sound.

## Pieces

| File         | Job |
|--------------|-----|
| `RUN-buyback-watch.cmd` | double‑click launcher (no terminal, no settings changes) |
| `watch.ps1`  | polls the URL, downloads + parses the PDF, writes `data/state.json`, **and serves the page** in the same window |
| `start.ps1`  | thin wrapper around `watch.ps1` that also opens the browser |
| `serve.ps1`  | stand‑alone static server (only needed if you run the page separately) |
| `index.html` / `app.js` / `style.css` | the alert page (polls `data/state.json` every 3 s) |
| `data/`      | downloaded PDF + `state.json` (git‑ignored) |

### Test the parser on its own

```bash
powershell -ExecutionPolicy Bypass -File watch.ps1 -TestPdf .\data\sample_BBPA_20250604.pdf
```

Writes a `found` `state.json` from a real past announcement so you can see the
full alert without waiting.

```bash
powershell -ExecutionPolicy Bypass -File watch.ps1 -SelfTest
```

Runs assertions on the amount / tier / formatting logic ($500M, $2B, $12.5B).

## Notes

- PDF text is extracted with `pdftotext` (already on this machine via Git for
  Windows). If it ever can't read the amount, the alert still fires and shows a
  "open the PDF to confirm" note.
- The amount picked is the first `$` figure over $10M that appears after the
  words "Maximum Par Amount to be Redeemed" (falls back to the largest `$` figure
  in the doc). The $1,000,000 minimum‑offer line is ignored. There is no upper
  bound. Treasury can buy back *less* than this announced maximum.
- Polling every 20 s against a public government file is light, but don't crank
  the interval down to 1 s and leave it for days.
- The PC has to be awake with this window + the browser tab open. If it sleeps,
  polling pauses until it wakes.
- The desktop notification needs the one‑time **Enable** click and the OS/browser
  set to allow notifications. The full‑screen colour, the sound, and the flashing
  tab title do not depend on that.
