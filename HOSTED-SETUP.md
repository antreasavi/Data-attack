# Buyback Watch — hosted version (GitHub Pages + Cloudflare Worker)

Open one URL from any device. A tiny free Cloudflare Worker does the actual
fetch of the TreasuryDirect PDF (their server blocks browsers with no CORS
headers); the GitHub Pages page polls through it, reads the buyback dollar
amount out of the PDF, and flashes a full‑screen colour + sound + notification.

```
your phone / laptop  ─▶  GitHub Pages page (docs/)  ─▶  Cloudflare Worker  ─▶  treasurydirect.gov PDF
```

Watched file: `BBPA_20260910174000.pdf` (Sept 10 operation). Anything dated
before **2026‑09‑10** is ignored, so the already‑published Sept 9 $12.5B
announcement will **not** trigger it. To watch a different one, edit
`TARGET_URL` and `NOT_BEFORE` at the top of `docs/app.js`.

---

## 1. Turn on GitHub Pages (one time)

1. Push this repo (the `docs/` folder must be on the `main` branch).
2. GitHub repo → **Settings** → **Pages**.
3. **Source:** *Deploy from a branch* → Branch **main** → Folder **/docs** → **Save**.
4. Wait ~1 min. Your page is at:
   `https://antreasavi.github.io/Data-attack/`

## 2. Deploy the Cloudflare Worker (one time, ~2 min, free)

1. Sign up / log in at <https://dash.cloudflare.com> (free plan is fine).
2. **Workers & Pages** → **Create** → **Workers** → **Create Worker**.
3. Give it a name, e.g. `buyback-proxy` → **Deploy**.
4. Click **Edit code**. Delete everything in the editor.
5. Open `cloudflare-worker.js` from this repo, copy all of it, paste it in.
6. **Deploy**.
7. Copy the Worker URL shown — looks like
   `https://buyback-proxy.YOURNAME.workers.dev`

## 3. Connect them (one time)

1. Open your GitHub Pages URL.
2. It asks for the Worker URL — paste the `…workers.dev` address → **Save & start**.
   (Stored in that browser only. Use **Change Worker URL** later if needed.)
3. Click **Enable sound + notifications** once and allow the browser prompt.
4. Leave the tab open. **Preview alert** shows what a hit looks like.

---

## When the announcement drops

Within ~20 seconds the page:

- floods the screen with a colour by size — blue `<$1B`, green `$1B–3B`,
  orange `$3B–5B`, red `$5B–10B`, dark red `≥$10B`
- shows the amount huge (`$12.5B` and `$12,500,000,000`)
- shows operation type, maturity range, operation date, a link to the PDF
- plays a repeating beep, pops a desktop notification, flashes the tab title
- **Acknowledge** stops the flashing + sound

## Notes / limits

- The Worker free plan allows 100,000 requests/day. This uses a few thousand.
- The Worker only proxies `…/BBPA_<14 digits>.pdf` on treasurydirect.gov /
  fiscaldata.treasury.gov — it is not an open proxy.
- The tab must stay open on a device that's awake. Notifications need the
  one‑time **Enable** click; the colour + sound + title flash don't.
- Polls the exact file plus the same name up to 2 days later, the other usual
  close‑time stamps, and the fiscaldata mirror — so a small date/time slip in
  the filename still gets caught, but nothing before `NOT_BEFORE` is accepted.
- The local PowerShell version in `buyback-watcher/` still works and polls
  faster (20 s, no proxy) if you'd rather run it on one PC.
