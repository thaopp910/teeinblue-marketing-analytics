# Teeinblue Marketing Analytics

Self-built marketing dashboard (a lightweight "Looker of our own"). A static
front-end (`index.html`, Chart.js) renders KPIs, charts and filters per channel.
Data comes from **GA4 (Analytics Data API)** and **Google Search Console API**,
pulled by a Python script into `data.json` — no Google Sheet, no always-on server.

## Channels (top nav)

- **Website** — GA4 (users/sessions/pageviews) + GSC (clicks/impressions/CTR/position)
- **Blogs** — same, filtered to `/blogs` paths
- **App Store / Advertising / Social / Email** — planned (own sources)

## Run locally

```bash
python3 -m http.server 4599
# open http://localhost:4599/index.html
```

The dashboard currently ships with **mock data** shaped exactly like the real
GA4 + GSC output, so it runs immediately. Swap to real data with the fetch step.

## Real data (GA4 + GSC)

Prereqs (one-time):
1. **GA4 Property ID** (Analytics → Admin → Property Settings).
2. **GSC property** (e.g. `https://teeinblue.com/`).
3. A **Google Cloud service account** with **Analytics Data API** + **Search
   Console API** enabled, added as a **Viewer** on the GA4 property and as a user
   in Search Console. Download its **JSON key** to `ga-key.json` (git-ignored).

Then (script provided in a later step):

```bash
pip3 install google-analytics-data google-api-python-client google-auth
python3 ga4_gsc_fetch.py   # writes data.json
```

> ⚠️ Never commit `ga-key.json` — it is in `.gitignore`.
