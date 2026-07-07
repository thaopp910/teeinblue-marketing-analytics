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

- **`ga4_gsc_fetch.py` written** — pulls GA4 (property `307498741`) + GSC
  (`sc-domain:teeinblue.com`) and writes `data.json` in the exact front-end shape.
  Config via env vars (see the script header). Deps in `requirements.txt`; a `.venv`
  is set up. Run: `.venv/bin/python ga4_gsc_fetch.py`.
- **`index.html` now `fetch('data.json')`** at startup (`loadData()`), with the
  procedural mock kept as an offline fallback (`buildMock()`). A src badge shows which
  source is live (green dot = data.json, amber = mock). Verified both paths in preview.
- Channels: **Website** (`scope:"all"`) and **Blogs** (`scope:"blog"`, filters to
  `/blogs` paths) are live `native` dashboards. **App Store / Advertising / Social /
  Email** are placeholders (`mode:"soon"`).
- **App Store is now a live GA4-only `native` channel** (GA4 property `374057963`);
  Advertising / Social / Email remain `mode:"soon"`.
- **Blocked on GCP setup:** service-account key authenticates fine, but the fetch
  fails until two APIs are enabled in project `teeinblue-marketing-analytics`
  (project number `724959032197`): **Google Analytics Data API** and **Search Console
  API**. Enable both, add the SA as Viewer on both GA4 properties (`307498741`,
  `374057963`) and as a user in Search Console, then run:
  `.venv/bin/python ga4_gsc_fetch.py`. GSC is a **domain** property →
  `sc-domain:teeinblue.com` (the script default). A `.venv` is already set up.
- Not yet done: enable the two APIs + first real run; Advertising/Social/Email channels.

## Data model (data.json — what `ga4_gsc_fetch.py` writes, what the front-end reads)

- `DAYS[]` — dates `"YYYY-MM-DD"` (front-end parses to `Date` via `new Date(s+'T00:00:00')`).
- `TOTALS` — **site-level** daily series `{users[], sessions[], views[], clicks[],
  impr[], posSum[]}` aligned to `DAYS`. This is the ACCURATE source for KPIs/charts.
- `USERS_PRESET` — `{ "7","28","90","ytd","all" : n }` — GA4 `activeUsers` queried
  per preset range (users are non-additive, so this is the only way to match GA4).
- `PAGES[]` — per page `{path, kind, users[], sessions[], views[], engaged[], clicks[],
  impr[], posSum[]}` — used for the Top-pages chart and the page-path filter only
  (capped at TOP_PAGES; does NOT drive KPI totals).
- `QUERIES[]` — per GSC query `{q, brand, clicks[], impr[], posSum[]}` (capped TOP_QUERIES).
- `blogs` — `{ daily:{…same 6 series…, filtered to /blogs}, usersPreset:{…} }` for the
  Blogs channel (GA4 `pagePath` begins-with `/blogs`; GSC `page` contains `/blogs`).
- `appstore` — `{ property, daily:{users[],sessions[],views[]}, usersPreset:{…},
  pages:[…] }` — GA4-only (no GSC).
- `posSum` = position × impressions (impression-weighted avg position;
  `Σ posSum / Σ impr` is exact for any range/page subset).

### Accuracy contract (why it's split this way)
- **Exact vs GA4/GSC** (additive metrics, from `TOTALS`/`blogs.daily`): Sessions,
  Pageviews, Clicks, Impressions, CTR, Position — for any date range.
- **Users**: exact per preset (from `USERS_PRESET`) when no custom path filter; the
  KPI shows the preset value and labels it "khớp GA4". With a custom path filter (or
  any per-page sum) Users/Sessions become approximate (labeled "≈ ước lượng") — GA4
  de-dups users cross-day AND cross-page, which a static per-page export can't replicate.
- Front-end (`renderNative` in `index.html`): `useExact = !!D.daily && !filterText`.
  Exact path reads `TOTALS`/`blogs.daily` + `usersPreset`; else falls back to per-page
  `agg()`. Deltas always use the daily-sum series for a consistent baseline.
- `rangeIdx()` preset ranges MUST match `preset_ranges()` in the fetch script.

## Real data setup (GA4 + GSC) — CONFIRMED VALUES

- **GA4 website property:** `307498741` (env `GA4_PROPERTY`).
- **GA4 App Store property:** `374057963` (env `APPSTORE_PROPERTY`).
- **GSC:** domain property → `sc-domain:teeinblue.com` (env `GSC_SITE`).
- **Auth:** OAuth as the user (see the OAuth section below); a service-account key is the
  fallback. Both the key and OAuth secrets are git-ignored — Claude must never read/handle
  their contents. Ask the user for the service-account email / key path if needed.
- Deps in `requirements.txt`; a `.venv` is set up (`.venv/bin/python ga4_gsc_fetch.py`).
- All fetch behaviour is env-configurable (property ids, dates, GSC site, caps, out path) —
  see the header of `ga4_gsc_fetch.py`.

### Auth: OAuth as the user (chosen — SA lacks GA4 admin grant)
The user has read access to GA4/GSC but is NOT a GA4 Administrator, so the service
account can't be added as a Viewer. Instead the script authenticates **as the user**
via OAuth (`get_credentials()`), which needs no admin. Setup (one-time):
1. GCP Console → project `teeinblue-marketing-analytics` → APIs & Services → OAuth
   consent screen: User type **External**, app name + support/dev email, save; add the
   user's own Google account under **Test users**.
2. APIs & Services → Credentials → Create credentials → **OAuth client ID** →
   **Desktop app** → download JSON → save as **`oauth_client.json`** at repo root.
3. Run `.venv/bin/python ga4_gsc_fetch.py` → a browser opens once for consent →
   token cached to `token.json` (refreshes silently after). Both files are git-ignored.
`get_credentials()` auto-picks OAuth when `oauth_client.json`/`token.json` exists, else
service account. Force with `AUTH_MODE=oauth|sa`. One credential covers GA4 + GSC.

## Non-GA4/GSC channels

**App Store is now GA4-backed** (property `374057963`) — done. Advertising
(Shopify/Google/Reddit ads) / Social (Facebook Community) / Email still don't exist in
GA4/GSC. Their numbers live in the marketing tracker sheet:
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

1. **Enable the 2 GCP APIs** (Analytics Data + Search Console) in project
   `724959032197`, grant the SA access on both GA4 properties + Search Console.
2. Run `.venv/bin/python ga4_gsc_fetch.py` → generates real `data.json`; the site
   auto-switches from mock to live (green badge). Verify KPIs against GA4/GSC.
3. Schedule the fetch (cron/launchd) to refresh `data.json` on a cadence.
4. Build Advertising / Social / Email channels from the marketing sheet (later phase).

DONE: `ga4_gsc_fetch.py` (GA4+GSC, accuracy-split), `index.html` wired to `data.json`
with mock fallback, App Store GA4 channel, key git-ignored.
