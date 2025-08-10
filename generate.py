# OneCoolThing - auto blog generator (minimal, ASCII-safe)

import os, re, json, shutil, html, pathlib, random
from datetime import datetime, timezone
from urllib.parse import quote_plus
import requests

SITE_TITLE = "OneCoolThing"
SITE_DESC = "One fascinating thing a day - quick read, solid source."
POSTS_TO_KEEP_ON_INDEX = 20

KEYWORDS = ["science", "history", "animals", "microbiology", "engineering", "space", "ocean", "architecture", "materials"]

AFF_AMAZON_TAG = os.getenv("AFF_AMAZON_TAG", "")
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "")
BMAC_URL = os.getenv("BMAC_URL", "")

ROOT = pathlib.Path(__file__).parent.resolve()
OUT = ROOT / "site"
POSTS = OUT / "posts"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "OneCoolThingBot/1.0 (+https://github.com)"})

WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
WIKI_RANDOM = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
WIKI_SEARCH = "https://www.wiki  pedia.org/w/api.php?action=query&list=search&srsearch={}&format=json&srlimit=10".replace("  ", "")
WIKI_MEDIA  = "https://www.wikipedia.org/w/api.php?action=query&prop=pageimages|images&format=json&titles={}"
COMMONS_IMAGE = "https://commons.wikimedia.org/w/api.php?action=query&titles=File:{}&prop=imageinfo&iiprop=url&format=json"

def slugify(s):
    s = re.sub(r"[^a-zA-Z0-9\-\s]", "", s).strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s[:80] or "post"

def fetch_topic():
    kws = KEYWORDS[:]
    random.shuffle(kws)
    for kw in kws[:5]:
        r = SESSION.get(WIKI_SEARCH.format(quote_plus(kw)), timeout=20)
        if not r.ok:
            continue
        hits = r.json().get("query", {}).get("search", [])
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
    r = SESSION.get(WIKI_RANDOM, timeout=20)
    r.raise_for_status()
    return r.json()

def fetch_lead_image(title):
    try:
        r = SESSION.get(WIKI_MEDIA.format(quote_plus(title)), timeout=20)
        if not r.ok:
            return None
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for _, p in pages.items():
            imgs = p.get("images", []) or []
            for im in imgs:
                name = (im.get("title") or "").replace("File:", "")
                lower = name.lower()
                if not (lower.endswith(".jpg") or lower.endswith(".jpeg") or lower.endswith(".png") or lower.endswith(".webp")):
                    continue
                c = SESSION.get(COMMONS_IMAGE.format(quote_plus(name)), timeout=20)
                if not c.ok:
                    continue
                cd = c.json()
                for __, cp in cd.get("query", {}).get("pages", {}).items():
                    info = cp.get("imageinfo", [])
                    if info:
                        return info[0].get("url")
    except Exception:
        return None
    return None

def amazon_search_links(title):
    if not AFF_AMAZON_TAG:
        return []
    terms = ["book", "poster", "guide", "merch"]
    links = []
    for t in terms:
        q = quote_plus(title + " " + t)
        links.append(("Amazon: " + t.title(), "https://www.amazon.com/s?k=" + q + "&tag=" + AFF_AMAZON_TAG))
    return links

def adsense_block():
    if not ADSENSE_CLIENT:
        return ""
    return (
        "<div style=\"margin:20px 0\">"
        "<ins class=\"adsbygoogle\" style=\"display:block\" "
        "data-ad-client=\"" + html.escape(ADSENSE_CLIENT) + "\" "
        "data-ad-slot=\"auto\" data-ad-format=\"auto\" data-full-width-responsive=\"true\"></ins>"
        "<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script>"
        "</div>"
    )

def html_page(title, body, desc=""):
    ads = adsense_block()
    bmac = "<a href='" + html.escape(BMAC_URL) + "' target='_blank' rel='noopener'>Buy me a coffee</a>" if BMAC_URL else ""
    return (
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\"/><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
        "<title>" + html.escape(title) + " - " + html.escape(SITE_TITLE) + "</title>"
        "<meta name=\"description\" content=\"" + html.escape(desc or SITE_DESC) + "\"/>"
        "<link rel=\"alternate\" type=\"application/rss+xml\" title=\"" + html.escape(SITE_TITLE) + " RSS\" href=\"./rss.xml\"/>"
        "<style>"
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,sans-serif;line-height:1.6;margin:0;background:#fafafa;color:#111}"
        "header,footer{background:#fff;border-bottom:1px solid #eee}"
        ".wrap{max-width:840px;margin:0 auto;padding:22px}"
        "a{color:#0b66f4;text-decoration:none} a:hover{text-decoration:underline}"
        ".card{background:#fff;border:1px solid #eee;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 1px 0 rgba(0,0,0,.04)}"
        "img{max-width:100%;border-radius:12px}"
        ".grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}"
        ".muted{color:#666}"
        "</style>"
        "<script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + html.escape(ADSENSE_CLIENT) + "\" crossorigin=\"anonymous\"></script>"
        "</head><body>"
        "<header><div class=\"wrap\"><h1 style=\"margin:0\">" + html.escape(SITE_TITLE) + "</h1><div class=\"muted\">" + html.escape(SITE_DESC) + "</div></div></header>"
        "<main><div class=\"wrap\">" + body + ads + "</div></main>"
        "<footer><div class=\"wrap muted\">© " + str(datetime.now().year) + " • Built by automation. " + bmac + "</div></footer>"
        "</body></html>"
    )

def build_post(summary):
    title = summary.get("title") or summary.get("displaytitle") or "Interesting Topic"
    extract = summary.get("extract") or ""
    url = summary.get("content_urls", {}).get("desktop", {}).get("page") or summary.get("content_urls", {}).get("mobile", {}).get("page")
    img = summary.get("thumbnail", {}).get("source") or fetch_lead_image(title)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slugify(title)
    fname = ts + "-" + slug + ".html"
    path = POSTS / fname

    aff = amazon_search_links(title)
    aff_html = "".join(["<li><a href='" + html.escape(u) + "' target='_blank' rel='nofollow noopener'>" + html.escape(t) + "</a></li>" for t, u in aff])
    aff_block = "<div class='card'><strong>Related links</strong><ul>" + aff_html + "</ul></div>" if aff_html else ""

    img_html = "<img src=\"" + html.escape(img) + "\" alt=\"" + html.escape(title) + "\" />" if img else ""
    body = (
        "<article class=\"card\">"
        "<h1>" + html.escape(title) + "</h1>"
        "<div class=\"muted\">Source: <a href=\"" + html.escape(url or "#") + "\" target=\"_blank\" rel=\"noopener\">Wikipedia</a></div>"
        + img_html +
        "<p>" + html.escape(extract) + "</p>"
        "</article>"
        + aff_block
    )

    html_full = html_page(title, body, desc=extract[:150])
    path.write_text(html_full, encoding="utf-8")
    return fname, title, extract

def build_index(posts_meta):
    cards = []
    for m in posts_meta[:POSTS_TO_KEEP_ON_INDEX]:
        cards.append(
            "<a class=\"card\" href=\"./posts/{file}\">"
            "<div class=\"muted\">{date}</div>"
            "<h3 style=\"margin:.2rem 0 .4rem 0\">{title}</h3>"
            "<div class=\"muted\">{desc}</div>"
            "</a>".format(file=html.escape(m["file"]), date=html.escape(m["date"]), title=html.escape(m["title"]), desc=html.escape(m["desc"][:140]))
        )
    body = "<div class='grid'>" + "".join(cards) + "</div>"
    OUT.joinpath("index.html").write_text(html_page(SITE_TITLE, body, SITE_DESC), encoding="utf-8")

def build_rss(posts_meta):
    items = []
    for m in posts_meta[:50]:
        items.append(
            "<item>"
            "<title>" + html.escape(m['title']) + "</title>"
            "<link>./posts/" + html.escape(m['file']) + "</link>"
            "<guid>./posts/" + html.escape(m['file']) + "</guid>"
            "<pubDate>" + html.escape(m['rfc2822']) + "</pubDate>"
            "<description>" + html.escape(m['desc'][:500]) + "</description>"
            "</item>"
        )
    rss = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<rss version=\"2.0\"><channel>"
        "<title>" + html.escape(SITE_TITLE) + "</title>"
        "<link>./</link>"
        "<description>" + html.escape(SITE_DESC) + "</description>"
        + "".join(items) +
        "</channel></rss>"
    )
    OUT.joinpath("rss.xml").write_text(rss, encoding="utf-8")

def build_sitemap(posts_meta):
    urls = ["<url><loc>./</loc></url>"] + ["<url><loc>./posts/" + html.escape(m["file"]) + "</loc></url>" for m in posts_meta]
    sm = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        + "".join(urls) +
        "</urlset>"
    )
    OUT.joinpath("sitemap.xml").write_text(sm, encoding="utf-8")

def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    POSTS.mkdir(parents=True, exist_ok=True)

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
    print("Built", fname, "-", title)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            POSTS.mkdir(parents=True, exist_ok=True)
            OUT.mkdir(parents=True, exist_ok=True)
            fallback = "<div class='card'><h1>OneCoolThing</h1><p>First run pending or fetch error.</p><pre>" + html.escape(str(e)) + "</pre></div>"
            OUT.joinpath("index.html").write_text(html_page(SITE_TITLE, fallback, SITE_DESC), encoding="utf-8")
            OUT.joinpath("rss.xml").write_text("", encoding="utf-8")
            OUT.joinpath("sitemap.xml").write_text("", encoding="utf-8")
            print("Non-fatal error, published fallback:", e)
        except Exception as e2:
            print("Failsafe also failed:", e2)
            raise
