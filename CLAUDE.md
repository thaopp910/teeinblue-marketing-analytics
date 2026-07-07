# Teeinblue Marketing Analytics — Project Context

A **self-built marketing dashboard** ("a Looker of our own") for Teeinblue. A static
front-end renders KPIs, charts and filters per channel; data is pulled from **GA4**
and **Google Search Console** into a local `data.json` — no Google Sheet dependency,
no always-on server. Split out from the `teeinblue-pipeline` (blog automation) repo so
it lives on its own.

GitHub: https://github.com/thaopp910/teeinblue-marketing-analytics (public)

## Architecture

- **`index.html`** — single-file front-end. Top nav = channels. Each `native` channel
  renders a dashboard with Chart.js (KPIs + line/bar charts + a query table) and two
  client-side filters: **date range** and **page path contains**. No build step.
- **Data source (planned):** a Python script (`ga4_gsc_fetch.py`, not written yet)
  calls the **GA4 Analytics Data API** + **Search Console API** and writes **`data.json`**
  in the exact shape the front-end already uses (see Data model). Run it on a schedule
  to refresh; the site just reads the JSON.
- Brand color: `#1350de` (Teeinblue blue). GSC accent `#7a5af8`.

## Current status (as of this writing)

- Dashboard is **built and verified** but runs on **MOCK data** generated inline in
  `index.html` (procedural, shaped exactly like real GA4/GSC output).
- Channels: **Website** (`scope:"all"`) and **Blogs** (`scope:"blog"`, filters to
  `/blogs` paths) are live `native` dashboards. **App Store / Advertising / Social /
  Email** are placeholders (`mode:"soon"`).
- Not yet done: the real data pull (`ga4_gsc_fetch.py`), wiring `index.html` to fetch
  `data.json` instead of the inline mock, and the non-GA4 channels.

## Data model (mock now, real later — keep this shape in data.json)

- `DAYS[]` — array of dates (currently 2026-01-01 … 2026-07-04).
- `PAGES[]` — per page: `{path, kind, users[], sessions[], views[], engaged[],
  clicks[], impr[], posSum[]}` where each array is a per-day series aligned to `DAYS`.
  `posSum` = position × impressions (for weighted average position). GA4 gives
  users/sessions/views; GSC gives clicks/impr/position by page.
- `QUERIES[]` — per search query (GSC): `{q, brand, clicks[], impr[], posSum[]}`.
- Front-end aggregates over the selected date range and page-path filter, and computes
  deltas vs the immediately-preceding equal-length period.

## Real data setup (GA4 + GSC) — inputs needed from the user

1. **GA4 Property ID** (Analytics → Admin → Property Settings) — numeric.
2. **GSC property** — e.g. `https://teeinblue.com/` (or a domain property).
3. **Google Cloud service account** with **Analytics Data API** + **Search Console API**
   enabled, added as **Viewer** on the GA4 property and as a user in Search Console.
4. **JSON key** downloaded to `ga-key.json` at the repo root — **git-ignored, never
   commit it.** The fetch script reads it via a path/env var; Claude must never handle
   the key contents.

Fetch script deps (when writing it):
`pip3 install google-analytics-data google-api-python-client google-auth`

## Non-GA4/GSC channels

App Store / Advertising (Shopify/Google/Reddit ads) / Social (Facebook Community) /
Email don't exist in GA4/GSC. Their numbers live in the marketing tracker sheet:
https://docs.google.com/spreadsheets/d/15AOSU3itnybY4e41kZhicUp8_QofW-Yq9VNcNpYmtyw
Build those channels as `native` dashboards fed from that sheet (published CSV or a
pull script) in a later phase.

## Conventions

- Keep `index.html` self-contained and editable (no framework/build) — the whole point
  is that layout is controlled from HTML, not locked in Looker.
- Never commit secrets (`ga-key.json` is in `.gitignore`).
- Run locally: `python3 -m http.server 4599` → http://localhost:4599/index.html
  (preview config in `.claude/launch.json`).

## Next steps

1. Get the 4 inputs above from the user.
2. Write `ga4_gsc_fetch.py` → outputs `data.json`.
3. Refactor `index.html` to `fetch('data.json')` and drop the inline mock (keep a small
   mock fallback so it still renders offline).
4. Build App Store / Advertising / Social channels from the marketing sheet.
