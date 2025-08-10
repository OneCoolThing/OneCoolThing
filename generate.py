# ===============================
# File: generate.py  (paste this exact file)
# ===============================
"""
OneCoolThing – auto blog generator (GitHub Pages + Actions)
- Posts one Wikipedia-based article per run (daily by default)
- Optional monetization: Amazon affiliate search links, AdSense, BuyMeACoffee
- Zero hosting cost; runs on GitHub Actions; deploys to GitHub Pages

Setup summary (you are following this step-by-step in chat):
1) Create public repo named OneCoolThing
2) Add this file as generate.py
3) Add requirements.txt (below)
4) Add .github/workflows/site.yml (below)
5) Add README.md (below)
6) Turn on Pages: Settings → Pages → Source: GitHub Actions
7) Run the workflow once; then it runs daily automatically
"""

import os, re, json, shutil, html, pathlib
from datetime import datetime, timezone
from urllib.parse import quote_plus
import random
import requests

# ---------- Site branding ----------
SITE_TITLE = "OneCoolThing"
SITE_DESC = "One fascinating thing a day — quick read, solid source."
POSTS_TO_KEEP_ON_INDEX = 20

# Niche steering keywords (edit later if you want)
KEYWORDS = [
    "science", "history", "animals", "microbiology", "engineering", "space", "ocean", "architecture", "materials"
]

# ---------- Secrets (optional) ----------
AFF_AMAZON_TAG = os.getenv("AFF_AMAZON_TAG", "")  # e.g., yourtag-20
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "")  # e.g., ca-pub-xxxxxxxx
BMAC_URL = os.getenv("BMAC_URL", "")              # e.g., https://buymeacoffee.com/you

# ---------- Paths ----------
ROOT = pathlib.Path(__file__).parent.resolve()
OUT = ROOT / "site"
POSTS = OUT / "posts"
ASSETS = OUT / "assets"

# ---------- HTTP session ----------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "OneCoolThingBot/1.0 (+https://github.com)"})

# ---------- Wikipedia endpoints ----------
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
WIKI_RANDOM = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
WIKI_SEARCH = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={}&format=json&srlimit=10"
WIKI_MEDIA = "https://en.wikipedia.org/w/api.php?action=query&prop=pageimages|images&format=json&titles={}"
COMMONS_IMAGE = "https://commons.wikimedia.org/w/api.php?action=query&titles=File:{}&prop=imageinfo&iiprop=url&format=json"

# ---------- Helpers ----------
def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\-\s]", "", s).strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s[:80] or "post"


def fetch_topic() -> dict:
    """Prefer topics matching KEYWORDS; fall back to a random summary."""
    kws = KEYWORDS[:]
    random.shuffle(kws)
    for kw in kws[:5]:
        q = SESSION.get(WIKI_SEARCH.format(quote_plus(kw)), timeout=20)
        q.raise_for_status()
        hits = q.json().get("query", {}).get("search", [])
        random.shuffle(hits)
        for h in hits:
            title = h.get("title")
            if not title:
                continue
            s = SESSION.get(WIKI_SUMMARY.format(quote_plus(title)), timeout=20)
            if not s.ok:
                continue
            data = s.json()
            if data.get("type") == "standard" and len(data.get("extract", "")) > 400:
                return data
    # fallback
    r = SESSION.get(WIKI_RANDOM, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_lead_image(title: str) -> str | None:
    try:
        r = SESSION.get(WIKI_MEDIA.format(quote_plus(title)), timeout=20).json()
        pages = r.get("query", {}).get("pages", {})
        for _, p in pages.items():
            for im in p.get("images", []) or []:
                name = (im.get("title") or "").replace("File:", "")
                if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    continue
                c = SESSION.get(COMMONS_IMAGE.format(quote_plus(name)), timeout=20).json()
                for _, cp in c.get("query", {}).get("pages", {}).items():
                    info = cp.get("imageinfo", [])
                    if info:
                        return info[0].get("url")
    except Exception:
        return None
    return None


def amazon_search_links(title: str):
    if not AFF_AMAZON_TAG:
        return []
    terms = ["book", "poster", "guide", "merch"]
    links = []
    for t in terms:
        q = quote_plus(f"{title} {t}")
        links.append((f"Amazon: {t.title()}", f"https://www.amazon.com/s?k={q}&tag={AFF_AMAZON_TAG}"))
    return links


def adsense_block() -> str:
    if not ADSENSE_CLIENT:
        return ""
    return f"""
    <div style=\"margin:20px 0\">
      <ins class=\"adsbygoogle\" style=\"display:block\" data-ad-client=\"{html.escape(ADSENSE_CLIENT)}\" data-ad-slot=\"auto\" data-ad-format=\"auto\" data-full-width-responsive=\"true\"></ins>
      <script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script>
    </div>
    """


def html_page(title: str, body: str, desc: str = "") -> str:
    ads = adsense_block()
    bmac = f"<a href='{html.escape(BMAC_URL)}' target='_blank' rel='noopener'>Buy me a coffee</a>" if BMAC_URL else ""
    return f"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)} – {html.escape(SITE_TITLE)}</title>
<meta name="description" content="{html.escape(desc or SITE_DESC)}"/>
<link rel="alternate" type="application/rss+xml" title="{html.escape(SITE_TITLE)} RSS" href="./rss.xml"/>
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,sans-serif;line-height:1.6;margin:0;background:#fafafa;color:#111}}
  header,footer{{background:#fff;border-bottom:1px solid #eee}}
  .wrap{{max-width:840px;margin:0 auto;padding:22px}}
  a{{color:#0b66f4;text-decoration:none}} a:hover{{text-decoration:underline}}
  .card{{background:#fff;border:1px solid #eee;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 1px 0 rgba(0,0,0,.04)}}
  img{{max-width:100%;border-radius:12px}}
  .grid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}}
  .muted{{color:#666}}
</style>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={html.escape(ADSENSE_CLIENT)}" crossorigin="anonymous"></script>
</head>
<body>
<header><div class="wrap"><h1 style="margin:0">{html.escape(SITE_TITLE)}</h1><div class="muted">{html.escape(SITE_DESC)}</div></div></header>
<main><div class="wrap">{body}{ads}</div></main>
<footer><div class="wrap muted">© {datetime.now().year} • Built by automation. {bmac}</div></footer>
</body>
</html>
"""


def build_post(summary: dict):
    title = summary.get("title") or summary.get("displaytitle") or "Interesting Topic"
    extract = summary.get("extract") or ""
    url = summary.get("content_urls", {}).get("desktop", {}).get("page") or summary.get("content_urls", {}).get("mobile", {}).get("page")
    img = summary.get("thumbnail", {}).get("source") or fetch_lead_image(title)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slugify(title)
    fname = f"{ts}-{slug}.html"
    path = POSTS / fname

    aff = amazon_search_links(title)
    aff_html = "".join([f"<li><a href='{html.escape(u)}' target='_blank' rel='nofollow noopener'>{html.escape(t)}</a></li>" for t,u in aff])
    aff_block = f"<div class='card'><strong>Related links</strong><ul>{aff_html}</ul></div>" if aff_html else ""

    body = f"""
    <article class="card">
      <h1>{html.escape(title)}</h1>
      <div class="muted">Source: <a href="{html.escape(url or '#')}" target="_blank" rel="noopener">Wikipedia</a></div>
      {f'<img src="{html.escape(img)}" alt="{html.escape(title)}" />' if img else ''}
      <p>{html.escape(extract)}</p>
    </article>
    {aff_block}
    """

    html_full = html_page(title, body, desc=extract[:150])
    path.write_text(html_full, encoding="utf-8")
    return fname, title, extract


def build_index(posts_meta):
    cards = []
    for m in posts_meta[:POSTS_TO_KEEP_ON_INDEX]:
        cards.append(f"""
        <a class=\"card\" href=\"./posts/{html.escape(m['file'])}\">\n
          <div class=\"muted\">{html.escape(m['date'])}</div>
          <h3 style=\"margin:.2rem 0 .4rem 0\">{html.escape(m['title'])}</h3>
          <div class=\"muted\">{html.escape(m['desc'][:140])}</div>
        </a>
        """)
    body = f"<div class='grid'>{''.join(cards)}</div>"
    OUT.joinpath("index.html").write_text(html_page(SITE_TITLE, body, SITE_DESC), encoding="utf-8")


def build_rss(posts_meta):
    items = []
    for m in posts_meta[:50]:
        items.append(f"""
        <item>
          <title>{html.escape(m['title'])}</title>
          <link>./posts/{html.escape(m['file'])}</link>
          <guid>./posts/{html.escape(m['file'])}</guid>
          <pubDate>{html.escape(m['rfc2822'])}</pubDate>
          <description>{html.escape(m['desc'][:500])}</description>
        </item>
        """)
    rss = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>{html.escape(SITE_TITLE)}</title>
        <link>./</link>
        <description>{html.escape(SITE_DESC)}</description>
        {''.join(items)}
      </channel>
    </rss>
    """
    OUT.joinpath("rss.xml").write_text(rss.strip(), encoding="utf-8")


def build_sitemap(posts_meta):
    urls = ["<url><loc>./</loc></url>"]
    urls += [f"<url><loc>./posts/{html.escape(m['file'])}</loc></url>" for m in posts_meta]
    sm = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      {''.join(urls)}
    </urlset>
    """
    OUT.joinpath("sitemap.xml").write_text(sm.strip(), encoding="utf-8")


def main():
    # fresh output dir each run
    if OUT.exists():
        shutil.rmtree(OUT)
    POSTS.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    manifest_path = ROOT / "manifest.json"
    posts_meta = []
    if manifest_path.exists():
        try:
            posts_meta = json.loads(manifest_path.read_text("utf-8"))
        except Exception:
            posts_meta = []

    topic = fetch_topic()
    fname, title, extract = build_post(topic)

    now = datetime.now(timezone.utc)
    meta = {
        "file": fname,
        "title": title,
        "desc": extract,
        "date": now.strftime("%Y-%m-%d"),
        "rfc2822": now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
    }
    posts_meta = [meta] + posts_meta
    posts_meta = posts_meta[:365]

    build_index(posts_meta)
    build_rss(posts_meta)
    build_sitemap(posts_meta)

    manifest_path.write_text(json.dumps(posts_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {fname} – {title}")

if __name__ == "__main__":
    main()


# ===============================
# File: requirements.txt  (paste this exact content)
# ===============================
requests==2.32.3


# ===============================
# File: .github/workflows/site.yml  (create folders and paste this)
# ===============================
name: Build and Publish Site
on:
  push:
    branches: [ main ]
  workflow_dispatch: {}
  schedule:
    - cron: "0 14 * * *"   # runs daily at 14:00 UTC

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.x"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Build site
        env:
          AFF_AMAZON_TAG: ${{ secrets.AFF_AMAZON_TAG }}
          ADSENSE_CLIENT: ${{ secrets.ADSENSE_CLIENT }}
          BMAC_URL: ${{ secrets.BMAC_URL }}
        run: |
          python generate.py

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    needs: build
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4


# ===============================
# File: README.md  (paste this)
# ===============================
# OneCoolThing – Auto Blog (Free)

Daily, automated posts sourced from Wikipedia (summary + image). Deploys on GitHub Pages via Actions.

## Monetization (optional)
- Amazon Associates: add repo secret `AFF_AMAZON_TAG` (e.g., `yourtag-20`).
- Google AdSense: add repo secret `ADSENSE_CLIENT` (e.g., `ca-pub-XXXXXXXX`).
- BuyMeACoffee: add repo secret `BMAC_URL` with your page URL.

## How to run
1. Add these files to a **public** repo named `OneCoolThing`.
2. Repo → **Settings → Pages** → Source: **GitHub Actions**.
3. Go to **Actions** and run the workflow once. Site appears at:
   `https://<your-username>.github.io/OneCoolThing/`

## Change niche
Edit `KEYWORDS` in `generate.py`.
