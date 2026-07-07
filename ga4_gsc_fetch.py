#!/usr/bin/env python3
"""
ga4_gsc_fetch.py — Kéo GA4 (Analytics Data API) + Google Search Console và ghi
data.json cho index.html.

ĐỘ CHÍNH XÁC (khớp GA4/GSC, không lệch):
  - Sessions / Pageviews / Clicks / Impressions / CTR / Vị trí: lấy ở CẤP SITE
    (truy vấn theo ngày, KHÔNG tách theo trang) => cộng theo khoảng ngày là
    KHỚP TUYỆT ĐỐI số GA4/GSC (các metric này cộng gộp được theo ngày).
  - Users (GA4): KHÔNG cộng gộp được (GA4 khử trùng lặp người dùng chéo ngày).
    Vì vậy script truy vấn RIÊNG cho từng preset (7/28/90/YTD/all) => KPI Users
    khớp tuyệt đối GA4 khi không lọc path. Khi lọc path tùy ý -> xấp xỉ (per-page).
  - Per-page & per-query chỉ dùng cho bảng/biểu đồ Top và bộ lọc path; giới hạn
    TOP_PAGES / TOP_QUERIES KHÔNG ảnh hưởng tới KPI tổng (tổng lấy từ cấp site).

Chạy:
    pip3 install -r requirements.txt
    python3 ga4_gsc_fetch.py

Xác thực (2 cách, tự động chọn):
    - OAuth (mặc định nếu có oauth_client.json/token.json) — đăng nhập bằng tài khoản
      Google của bạn; KHÔNG cần quyền Admin GA4, chỉ cần tài khoản xem được dữ liệu.
      Lần đầu mở trình duyệt để cấp quyền, sau đó lưu token.json để chạy lại tự động.
    - Service account (nếu có key & AUTH_MODE=sa) — cần SA được thêm làm Viewer.

Env (đều có default cho Teeinblue):
    AUTH_MODE           "oauth" | "sa" | rỗng (auto)
    OAUTH_CLIENT        OAuth client 'Desktop' JSON  — mặc định oauth_client.json
    OAUTH_TOKEN         token cache                  — mặc định token.json
    GA_KEY_PATH         JSON key service account
    GA4_PROPERTY        GA4 website property        — mặc định 307498741
    APPSTORE_PROPERTY   GA4 App Store property       — mặc định 374057963
    GSC_SITE            GSC domain property          — mặc định sc-domain:teeinblue.com
    START_DATE          YYYY-MM-DD                   — mặc định 2026-01-01
    END_DATE            YYYY-MM-DD                   — mặc định hôm qua
    TOP_PAGES           số trang giữ lại             — mặc định 200
    TOP_QUERIES         số truy vấn giữ lại          — mặc định 100
    OUT                 file output                  — mặc định data.json

Script tự đọc key qua thư viện Google; KHÔNG in nội dung key ra ngoài.
"""

import os
import sys
import json
import datetime as dt
from urllib.parse import urlparse

# ----------------------------------------------------------------------------
# Cấu hình
# ----------------------------------------------------------------------------
KEY_PATH          = os.environ.get("GA_KEY_PATH",
                       "teeinblue-marketing-analytics-6fd7f3873307.json")
# OAuth (đăng nhập bằng chính tài khoản Google của bạn — không cần quyền Admin GA4)
OAUTH_CLIENT      = os.environ.get("OAUTH_CLIENT", "oauth_client.json")
OAUTH_TOKEN       = os.environ.get("OAUTH_TOKEN", "token.json")
AUTH_MODE         = os.environ.get("AUTH_MODE", "").lower()  # "oauth" | "sa" | "" (auto)
GA4_PROPERTY      = os.environ.get("GA4_PROPERTY", "307498741")
APPSTORE_PROPERTY = os.environ.get("APPSTORE_PROPERTY", "374057963")
GSC_SITE          = os.environ.get("GSC_SITE", "sc-domain:teeinblue.com")

_yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
START_DATE  = os.environ.get("START_DATE", "2026-01-01")
END_DATE    = os.environ.get("END_DATE", _yesterday)

TOP_PAGES   = int(os.environ.get("TOP_PAGES", "200"))
TOP_QUERIES = int(os.environ.get("TOP_QUERIES", "100"))
OUT         = os.environ.get("OUT", "data.json")

GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
SCOPES    = [GA4_SCOPE, GSC_SCOPE]           # 1 credentials dùng chung GA4 + GSC

BLOG_PREFIX = "/blogs"                       # phân loại blog (khớp front-end)
GA_METRICS  = ["activeUsers", "sessions", "screenPageViews", "engagedSessions"]

# Nguồn AI chatbot (khớp sessionSource GA4 theo substring, gồm cả subdomain)
AI_MARKERS = ["chatgpt", "openai.com", "perplexity", "gemini.google", "bard.google",
              "claude.ai", "copilot", "you.com", "poe.com", "deepseek", "x.ai",
              "grok", "meta.ai", "mistral"]


# ----------------------------------------------------------------------------
# Helpers chung
# ----------------------------------------------------------------------------
def daterange(start, end):
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    out, d = [], s
    while d <= e:
        out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def preset_ranges(start, end):
    """Khoảng ngày cho từng preset — PHẢI khớp rangeIdx() ở index.html."""
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)

    def clamp(d):
        return max(d, s).isoformat()

    return {
        "7":   (clamp(e - dt.timedelta(days=6)),  end),
        "28":  (clamp(e - dt.timedelta(days=27)), end),
        "90":  (clamp(e - dt.timedelta(days=89)), end),
        "ytd": (clamp(dt.date(e.year, 1, 1)),     end),
        "all": (start, end),
    }


def ga_date(v):
    return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"


def norm_path(path):
    if not path:
        return "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def url_to_path(url):
    return norm_path(urlparse(url).path)


def classify(path):
    if path == "/":
        return "home"
    if path.startswith("/products/"):
        return "product"
    if path.startswith("/collections/"):
        return "collection"
    if path.startswith(BLOG_PREFIX):
        return "blog"
    return "other"


def is_brand(q):
    return "teeinblue" in q.lower().replace(" ", "")


def fail(msg):
    print(f"\n[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


# ----------------------------------------------------------------------------
# GA4
# ----------------------------------------------------------------------------
def ga4_import():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        RunReportRequest, DateRange, Dimension, Metric, Filter, FilterExpression,
    )
    return (BetaAnalyticsDataClient, RunReportRequest, DateRange, Dimension,
            Metric, Filter, FilterExpression)


def ga4_blog_filter():
    (_, _, _, _, _, Filter, FilterExpression) = ga4_import()
    return FilterExpression(filter=Filter(
        field_name="pagePath",
        string_filter=Filter.StringFilter(
            match_type=Filter.StringFilter.MatchType.BEGINS_WITH,
            value=BLOG_PREFIX)))


def ga4_ai_filter():
    """FilterExpression: sessionSource CHỨA bất kỳ marker AI nào (or-group)."""
    from google.analytics.data_v1beta.types import (
        Filter, FilterExpression, FilterExpressionList)

    def contains(v):
        return FilterExpression(filter=Filter(
            field_name="sessionSource",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.CONTAINS, value=v)))

    return FilterExpression(or_group=FilterExpressionList(
        expressions=[contains(m) for m in AI_MARKERS]))


def ga4_and(a, b):
    from google.analytics.data_v1beta.types import FilterExpression, FilterExpressionList
    return FilterExpression(and_group=FilterExpressionList(expressions=[a, b]))


def ga4_ai_views(client, prop, start, end, day_idx, ndays, extra_filter=None):
    """Views theo ngày từ các nguồn AI chatbot, tách theo sessionSource.

    Trả về {bySource:{<source>:[daily]}, total:[daily]} — total gộp mọi nguồn AI,
    bySource giữ top 8 nguồn nhiều view nhất (để hiển thị)."""
    flt = ga4_ai_filter()
    if extra_filter is not None:
        flt = ga4_and(flt, extra_filter)
    rows = ga4_report(client, prop, ["date", "sessionSource"],
                      ["screenPageViews"], start, end, flt)
    by_source, total = {}, [0] * ndays
    for r in rows:
        i = day_idx.get(ga_date(r.dimension_values[0].value))
        if i is None:
            continue
        src = r.dimension_values[1].value
        v = int(float(r.metric_values[0].value))
        by_source.setdefault(src, [0] * ndays)[i] += v
        total[i] += v
    top = sorted(by_source.items(), key=lambda kv: sum(kv[1]), reverse=True)[:8]
    return {"bySource": {k: v for k, v in top}, "total": total}


def ga4_report(client, prop, dims, mets, start, end, dim_filter=None):
    (_, RunReportRequest, DateRange, Dimension, Metric, _, _) = ga4_import()
    rows, offset, page = [], 0, 100000
    while True:
        req = RunReportRequest(
            property=f"properties/{prop}",
            date_ranges=[DateRange(start_date=start, end_date=end)],
            dimensions=[Dimension(name=d) for d in dims],
            metrics=[Metric(name=m) for m in mets],
            dimension_filter=dim_filter,
            limit=page, offset=offset,
        )
        resp = client.run_report(req)
        rows.extend(resp.rows)
        offset += len(resp.rows)
        if len(resp.rows) < page or offset >= resp.row_count:
            break
    return rows


def ga4_scalar_users(client, prop, start, end, dim_filter=None):
    """activeUsers tổng cho đúng khoảng ngày (khử trùng lặp) — 1 con số."""
    rows = ga4_report(client, prop, [], ["activeUsers"], start, end, dim_filter)
    return int(float(rows[0].metric_values[0].value)) if rows else 0


def ga4_daily_users_sessions_views(client, prop, start, end, day_idx, ndays,
                                   dim_filter=None):
    """Chuỗi theo ngày: users(activeUsers), sessions, views."""
    rows = ga4_report(client, prop, ["date"],
                      ["activeUsers", "sessions", "screenPageViews"],
                      start, end, dim_filter)
    users = [0] * ndays
    sessions = [0] * ndays
    views = [0] * ndays
    for r in rows:
        i = day_idx.get(ga_date(r.dimension_values[0].value))
        if i is None:
            continue
        m = r.metric_values
        users[i]    = int(float(m[0].value))
        sessions[i] = int(float(m[1].value))
        views[i]    = int(float(m[2].value))
    return users, sessions, views


def ga4_pages(client, prop, start, end, day_idx, ndays):
    """Per-page-per-day (users/sessions/views/engaged)."""
    rows = ga4_report(client, prop, ["date", "pagePath"], GA_METRICS,
                      start, end)
    pages = {}
    for r in rows:
        i = day_idx.get(ga_date(r.dimension_values[0].value))
        if i is None:
            continue
        path = norm_path(r.dimension_values[1].value)
        pg = pages.get(path)
        if pg is None:
            pg = pages[path] = {
                "path": path, "kind": classify(path),
                "users": [0] * ndays, "sessions": [0] * ndays,
                "views": [0] * ndays, "engaged": [0] * ndays,
            }
        m = r.metric_values
        pg["users"][i]    += int(float(m[0].value))
        pg["sessions"][i] += int(float(m[1].value))
        pg["views"][i]    += int(float(m[2].value))
        pg["engaged"][i]  += int(float(m[3].value))
    return pages


# ----------------------------------------------------------------------------
# GSC
# ----------------------------------------------------------------------------
def gsc_client(creds):
    from googleapiclient.discovery import build
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def gsc_query(service, dimensions, filters=None):
    rows, start_row, row_limit = [], 0, 25000
    while True:
        body = {
            "startDate": START_DATE, "endDate": END_DATE,
            "dimensions": dimensions, "rowLimit": row_limit,
            "startRow": start_row, "dataState": "all",
        }
        if filters:
            body["dimensionFilterGroups"] = [{"filters": filters}]
        resp = service.searchanalytics().query(siteUrl=GSC_SITE, body=body).execute()
        r = resp.get("rows", [])
        rows.extend(r)
        if len(r) < row_limit:
            break
        start_row += row_limit
    return rows


def gsc_daily(service, day_idx, ndays, filters=None):
    """Chuỗi theo ngày cấp site: clicks / impr / posSum(=position*impr)."""
    rows = gsc_query(service, ["date"], filters)
    clicks = [0] * ndays
    impr = [0] * ndays
    posSum = [0.0] * ndays
    for r in rows:
        i = day_idx.get(r["keys"][0])
        if i is None:
            continue
        cl = int(r.get("clicks", 0))
        im = int(r.get("impressions", 0))
        clicks[i] = cl
        impr[i]   = im
        posSum[i] = round(r.get("position", 0.0) * im, 1)
    return clicks, impr, posSum


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def get_credentials():
    """1 credentials dùng chung cho GA4 + GSC.

    - Mặc định: OAuth (đăng nhập bằng tài khoản Google của bạn) nếu có oauth_client.json
      hoặc token.json — KHÔNG cần quyền Admin GA4, chỉ cần tài khoản xem được dữ liệu.
    - Hoặc service account nếu có key và AUTH_MODE=sa (yêu cầu SA được thêm làm Viewer).
    """
    mode = AUTH_MODE
    if not mode:
        mode = "oauth" if (os.path.exists(OAUTH_CLIENT) or os.path.exists(OAUTH_TOKEN)) \
               else ("sa" if os.path.exists(KEY_PATH) else "")

    if mode == "sa":
        from google.oauth2 import service_account
        if not os.path.exists(KEY_PATH):
            fail(f"AUTH_MODE=sa nhưng không thấy key {KEY_PATH}.")
        return service_account.Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)

    if mode == "oauth":
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
        except ImportError:
            fail("Thiếu google-auth-oauthlib. Chạy: pip3 install -r requirements.txt")
        creds = None
        if os.path.exists(OAUTH_TOKEN):
            creds = Credentials.from_authorized_user_file(OAUTH_TOKEN, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(OAUTH_CLIENT):
                    fail(f"Cần {OAUTH_CLIENT} (OAuth Client 'Desktop' tải từ Google Cloud). "
                         f"Xem hướng dẫn ở phần OAuth trong CLAUDE.md.")
                flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CLIENT, SCOPES)
                # Mở trình duyệt để bạn đăng nhập & cấp quyền (chỉ 1 lần)
                creds = flow.run_local_server(port=0)
            with open(OAUTH_TOKEN, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        return creds

    fail("Không có cách xác thực nào: cần oauth_client.json (OAuth) hoặc key service "
         "account. Đặt AUTH_MODE=oauth|sa nếu muốn chỉ định.")


def main():
    try:
        creds = get_credentials()
    except Exception as e:  # noqa: BLE001
        fail(f"Xác thực lỗi ({type(e).__name__}): {e}")
    ga_creds = gsc_creds = creds        # dùng chung 1 credentials

    DAYS = daterange(START_DATE, END_DATE)
    day_idx = {d: i for i, d in enumerate(DAYS)}
    ndays = len(DAYS)
    presets = preset_ranges(START_DATE, END_DATE)
    print(f"Khoảng ngày: {START_DATE} → {END_DATE} ({ndays} ngày)")

    (BetaAnalyticsDataClient, *_rest) = ga4_import()
    ga = BetaAnalyticsDataClient(credentials=ga_creds)

    # ============================ WEBSITE (GA4) ============================
    print(f"GA4 website {GA4_PROPERTY}…")
    try:
        w_users, w_sessions, w_views = ga4_daily_users_sessions_views(
            ga, GA4_PROPERTY, START_DATE, END_DATE, day_idx, ndays)
        w_users_preset = {k: ga4_scalar_users(ga, GA4_PROPERTY, s, e)
                          for k, (s, e) in presets.items()}
        w_pages = ga4_pages(ga, GA4_PROPERTY, START_DATE, END_DATE, day_idx, ndays)
        w_ai = ga4_ai_views(ga, GA4_PROPERTY, START_DATE, END_DATE, day_idx, ndays)
        # Blogs (lọc pagePath begins_with /blogs)
        bf = ga4_blog_filter()
        b_users, b_sessions, b_views = ga4_daily_users_sessions_views(
            ga, GA4_PROPERTY, START_DATE, END_DATE, day_idx, ndays, bf)
        b_users_preset = {k: ga4_scalar_users(ga, GA4_PROPERTY, s, e, bf)
                          for k, (s, e) in presets.items()}
        b_ai = ga4_ai_views(ga, GA4_PROPERTY, START_DATE, END_DATE, day_idx, ndays,
                            ga4_blog_filter())
    except Exception as e:  # noqa: BLE001
        fail(f"GA4 website lỗi ({type(e).__name__}): {e}\n"
             f"Kiểm tra: property {GA4_PROPERTY} đúng, Analytics Data API đã bật, "
             f"service account là Viewer trên property.")

    # ============================ WEBSITE (GSC) ============================
    print(f"GSC {GSC_SITE}…")
    try:
        gsc = gsc_client(gsc_creds)
        w_clicks, w_impr, w_posSum = gsc_daily(gsc, day_idx, ndays)
        gsc_page_rows  = gsc_query(gsc, ["date", "page"])
        gsc_query_rows = gsc_query(gsc, ["date", "query"])
        # Blogs GSC (page contains /blogs)
        blog_gf = [{"dimension": "page", "operator": "contains",
                    "expression": BLOG_PREFIX}]
        b_clicks, b_impr, b_posSum = gsc_daily(gsc, day_idx, ndays, blog_gf)
    except Exception as e:  # noqa: BLE001
        fail(f"GSC lỗi ({type(e).__name__}): {e}\n"
             f"Kiểm tra: Search Console API đã bật, service account là user "
             f"trong Search Console, GSC_SITE đúng (sc-domain:teeinblue.com "
             f"cho domain property; https://teeinblue.com/ cho URL-prefix).")

    # ---- Ghép per-page: thêm clicks/impr/posSum từ GSC vào w_pages ----
    for pg in w_pages.values():
        pg.setdefault("clicks", [0] * ndays)
        pg.setdefault("impr", [0] * ndays)
        pg.setdefault("posSum", [0.0] * ndays)
    for r in gsc_page_rows:
        i = day_idx.get(r["keys"][0])
        if i is None:
            continue
        path = url_to_path(r["keys"][1])
        pg = w_pages.get(path)
        if pg is None:
            pg = w_pages[path] = {
                "path": path, "kind": classify(path),
                "users": [0] * ndays, "sessions": [0] * ndays,
                "views": [0] * ndays, "engaged": [0] * ndays,
                "clicks": [0] * ndays, "impr": [0] * ndays,
                "posSum": [0.0] * ndays,
            }
        cl = int(r.get("clicks", 0))
        im = int(r.get("impressions", 0))
        pg["clicks"][i] += cl
        pg["impr"][i]   += im
        pg["posSum"][i] += r.get("position", 0.0) * im

    page_list = list(w_pages.values())
    page_list.sort(key=lambda p: sum(p["views"]) + sum(p.get("clicks", [])),
                   reverse=True)
    page_list = page_list[:TOP_PAGES]
    for p in page_list:
        p["posSum"] = [round(x, 1) for x in p["posSum"]]

    # ---- Queries ----
    queries = {}
    for r in gsc_query_rows:
        i = day_idx.get(r["keys"][0])
        if i is None:
            continue
        q = r["keys"][1]
        qq = queries.get(q)
        if qq is None:
            qq = queries[q] = {"q": q, "brand": is_brand(q),
                               "clicks": [0] * ndays, "impr": [0] * ndays,
                               "posSum": [0.0] * ndays}
        cl = int(r.get("clicks", 0))
        im = int(r.get("impressions", 0))
        qq["clicks"][i] += cl
        qq["impr"][i]   += im
        qq["posSum"][i] += r.get("position", 0.0) * im
    query_list = list(queries.values())
    query_list.sort(key=lambda q: sum(q["clicks"]), reverse=True)
    query_list = query_list[:TOP_QUERIES]
    for q in query_list:
        q["posSum"] = [round(x, 1) for x in q["posSum"]]

    # ============================ APP STORE (GA4 only) ====================
    print(f"GA4 App Store {APPSTORE_PROPERTY}…")
    try:
        a_users, a_sessions, a_views = ga4_daily_users_sessions_views(
            ga, APPSTORE_PROPERTY, START_DATE, END_DATE, day_idx, ndays)
        a_users_preset = {k: ga4_scalar_users(ga, APPSTORE_PROPERTY, s, e)
                          for k, (s, e) in presets.items()}
        a_pages = ga4_pages(ga, APPSTORE_PROPERTY, START_DATE, END_DATE,
                            day_idx, ndays)
        app_pages = sorted(a_pages.values(), key=lambda p: sum(p["views"]),
                           reverse=True)[:TOP_PAGES]
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] GA4 App Store {APPSTORE_PROPERTY} lỗi: {e} — bỏ qua kênh này.")
        a_users = a_sessions = a_views = None
        a_users_preset, app_pages = {}, []

    # ============================ GHI data.json ===========================
    out = {
        "meta": {
            "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "ga4_property": GA4_PROPERTY,
            "appstore_property": APPSTORE_PROPERTY,
            "gsc_site": GSC_SITE,
            "start": START_DATE, "end": END_DATE,
            "pages": len(page_list), "queries": len(query_list),
            "note": "Sessions/Views/Clicks/Impr/Position khớp tuyệt đối GA4/GSC. "
                    "Users chính xác theo preset khi không lọc path.",
        },
        "DAYS": DAYS,
        "TOTALS": {"users": w_users, "sessions": w_sessions, "views": w_views,
                   "clicks": w_clicks, "impr": w_impr, "posSum": w_posSum},
        "USERS_PRESET": w_users_preset,
        "AI": w_ai,
        "PAGES": page_list,
        "QUERIES": query_list,
        "blogs": {
            "daily": {"users": b_users, "sessions": b_sessions, "views": b_views,
                      "clicks": b_clicks, "impr": b_impr, "posSum": b_posSum},
            "usersPreset": b_users_preset,
            "ai": b_ai,
        },
    }
    if a_users is not None:
        out["appstore"] = {
            "property": APPSTORE_PROPERTY,
            "daily": {"users": a_users, "sessions": a_sessions, "views": a_views},
            "usersPreset": a_users_preset,
            "pages": app_pages,
        }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n✓ Ghi {OUT}")
    print(f"  Website: {len(page_list)} pages, {len(query_list)} queries · "
          f"Users(all)={w_users_preset.get('all')} · "
          f"AI views(all)={sum(w_ai['total'])} từ {len(w_ai['bySource'])} nguồn")
    print(f"  Blogs:   Users(all)={b_users_preset.get('all')} · "
          f"AI views(all)={sum(b_ai['total'])}")
    if a_users is not None:
        print(f"  AppStore:{len(app_pages)} pages · Users(all)={a_users_preset.get('all')}")


if __name__ == "__main__":
    main()
