# OneCoolThing - auto blog generator (ASCII-safe version)

import os, re, json, shutil, html, pathlib, random
from datetime import datetime, timezone
from urllib.parse import quote_plus
import requests

SITE_TITLE = "OneCoolThing"
SITE_DESC = "One fascinating thing a day - quick read, solid source."
POSTS_TO_KEEP_ON_INDEX = 20

# Niche steering keywords (edit later if you want)
KEYWORDS = ["science", "history", "animals", "microbiology", "engineering", "space", "ocean", "architecture", "materials"]

# Optional monetization via repo secrets
AFF_AMAZON_TAG = os.getenv("AFF_AMAZON_TAG", "")
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "")
BMAC_URL = os.getenv("BMAC_URL", "")

ROOT = pathlib.Path(__file__).parent.resolve()
OUT = ROOT / "site"
POSTS = OUT / "posts"
ASSETS = OUT / "assets"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "OneCoolThingBot/1.0 (+https://github.com)"})

WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
WIKI_RANDOM = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
WIKI_SEARCH = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={}&format=json&srlimit=10"
WIKI_MEDIA = "https://en.wikipedia.org/w/api.php?action=query&prop=pageimages|images&format=json&titles={}"
COMMONS_IMAGE = "https://commons.wikimedia.org/w/api.php?action=query&titles=File:{}&prop=imageinfo&iiprop=url&format=json"

def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\-\s]", "", s).strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s[:80] or "post"

def fetch_topic() -> dict:
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

def fetch_lead_image(title: str) -> str | None:
    try:
        r = SESSION.get(WIKI_MEDIA.format(quote_plus(title)), timeout=20).json()
        pages = r.get("query", {}).get("pages", {})
        for _, p in pages.items():
            for im in p.get("images", []) or []:
                name = (im.get("title") or "").replace("File:", "")
                if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    continue
                c = SESSION.get(COMMONS_IM_
