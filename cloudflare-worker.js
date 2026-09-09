/*
 * Buyback Watch - Cloudflare Worker
 * A tiny CORS proxy so the GitHub Pages alert page can read the TreasuryDirect
 * buyback announcement PDF (their server sends no CORS headers, so the browser
 * blocks it otherwise).
 *
 * It ONLY proxies TreasuryDirect / fiscaldata "BBPA_<14 digits>.pdf" URLs -
 * it is not an open proxy.
 *
 * Deploy (2 min, free):
 *   1. dash.cloudflare.com  ->  Workers & Pages  ->  Create  ->  Worker
 *   2. Name it (e.g. buyback-proxy), Deploy, then "Edit code"
 *   3. Replace everything with this file, Deploy
 *   4. Copy the URL (https://buyback-proxy.<you>.workers.dev) into the alert page
 *
 * Usage:
 *   GET  <worker>/?url=<pdf-url>&head=1   -> just the status code (fast check)
 *   GET  <worker>/?url=<pdf-url>          -> streams the PDF with CORS headers
 */

const ALLOW = /^https:\/\/(www\.treasurydirect\.gov|fiscaldata\.treasury\.gov)\/[\w.~!$&'()*+,;=:@/%-]*BBPA_\d{14}\.pdf$/;

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
  'Access-Control-Allow-Headers': '*',
  'Access-Control-Expose-Headers': 'X-Upstream-Status',
};

export default {
  async fetch(request) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS });
    }

    const u = new URL(request.url);
    const target = u.searchParams.get('url');
    const headOnly = u.searchParams.get('head') === '1';

    if (!target || !ALLOW.test(target)) {
      return new Response(
        JSON.stringify({ error: 'url missing or not an allowed TreasuryDirect BBPA PDF' }),
        { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } }
      );
    }

    let upstream;
    try {
      upstream = await fetch(target, {
        method: headOnly ? 'HEAD' : 'GET',
        headers: { 'User-Agent': 'buyback-watch/1.0', Accept: 'application/pdf,*/*' },
        cf: { cacheTtl: 0, cacheEverything: false },
      });
    } catch (e) {
      return new Response(
        JSON.stringify({ error: 'upstream fetch failed', detail: String(e) }),
        { status: 502, headers: { ...CORS, 'Content-Type': 'application/json' } }
      );
    }

    const headers = new Headers(CORS);
    headers.set('X-Upstream-Status', String(upstream.status));
    headers.set('Cache-Control', 'no-store');

    if (headOnly || !upstream.ok) {
      return new Response(headOnly ? null : `upstream ${upstream.status}`, {
        status: upstream.status,
        headers,
      });
    }

    const ct = upstream.headers.get('Content-Type');
    if (ct) headers.set('Content-Type', ct);
    const cl = upstream.headers.get('Content-Length');
    if (cl) headers.set('Content-Length', cl);
    return new Response(upstream.body, { status: 200, headers });
  },
};
