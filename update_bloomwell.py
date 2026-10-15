#!/usr/bin/env python3
"""Bloomwell (bloomwell.de) – public product teasers only.

Compliance notes (checked 2026-10-15):
- bloomwell.de/robots.txt: no Disallow -> public marketing pages may be fetched.
- The full product catalogue / live stock is the Flutter SPA app.bloomwell.de (marketplace),
  whose robots.txt is `User-agent: * Disallow: /`. We therefore do NOT call its API.
- We fetch ONE public page (https://bloomwell.de/) and parse the "Produktempfehlung" /
  product slider teasers (name, THC, CBD, "ab" price) + link-out to the marketplace item.
Output: bloomwell.json (normalized records, merged by merge_sources.py).
"""
import json, re, html, sys, time, datetime, pathlib, urllib.request, urllib.robotparser
HERE = pathlib.Path(__file__).parent
OUT = HERE / "bloomwell.json"
UA = "BliskoPriceBot/1.0 (+https://github.com/mikry119-cloud/blisko-ceny)"
URL = "https://bloomwell.de/"

def allowed(url):
    rp = urllib.robotparser.RobotFileParser("https://bloomwell.de/robots.txt"); rp.read()
    return rp.can_fetch(UA, url)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de"})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read().decode("utf-8", "replace")

def txt(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", s))).replace("\u200d", "")
def num(s): return float(s.replace(",", ".")) if s is not None else None

def parse(page):
    recs, seen = [], set()
    for m in re.finditer(r'href="(https://app\.bloomwell\.de/marketplace/(\d+))"', page):
        url, pid = m.group(1), m.group(2)
        if pid in seen: continue
        a_end = page.find("</a>", m.end())
        inner = txt(page[page.find(">", m.end()) + 1:a_end])
        raw = page[max(0, m.start() - 1500):m.start()]; ctx = txt(raw[:raw.rfind("<")])
        name = thc = cbd = cbd_max = price = None; unit = "g"
        # variant 1: info inside the <a> ("NAME (THC 26% / CBD 1%) ab 6,49€ / pro 1g")
        r = re.search(r"^\s*\|?\s*(.+?)\s*\(THC\s*([\d.,]+)%\s*/\s*CBD\s*([\d.,]+)%\)\s*\|?\s*ab\s*([\d.,]+)\s*€\s*/\s*pro\s*1\s*(\w+)", re.sub(r"(\s*\|\s*)+", " | ", inner))
        if r:
            name = re.sub(r"\s*\|\s*", " ", r.group(1)).strip(); thc, cbd, price = num(r.group(2)), num(r.group(3)), num(r.group(4)); unit = r.group(5)
        else:
            # variant 2: slider card before the link: "THC: 31 % CBD: 0 % - 1 % NAME ab 6.48 €"
            c = re.sub(r"(\s*\|\s*)+", " ", ctx)
            r = re.search(r"THC:\s*([\d.,]+)\s*%\s*CBD:\s*([\d.,]+)\s*%(?:\s*-\s*([\d.,]+)\s*%)?\s*(.+?)\s*ab\s*([\d.,]+)\s*€\s*$", c.strip())
            if not r: continue
            thc, cbd, cbd_max, name, price = num(r.group(1)), num(r.group(2)), num(r.group(3)), r.group(4).strip(), num(r.group(5))
        seen.add(pid)
        typ = "flower" if (thc or 0) <= 40 else "extract"
        recs.append({"name": name, "producer": "", "type": typ, "cultivar": name, "genetics": "",
                     "thc": thc, "cbd": cbd_max if cbd_max is not None else cbd, "terpenes": [],
                     "irradiated": None, "origin": "", "price_min": price, "price_max": None,
                     "unit": unit if typ == "flower" else "szt.", "availability": "unknown",
                     "src": "bloomwell", "source": "bloomwell.de", "url": url,
                     "note": "Teaser ze strony głównej bloomwell.de (cena 'ab'); pełny katalog tylko w aplikacji"})
    return recs

def main():
    if not allowed(URL): print("robots.txt disallows", URL, file=sys.stderr); return 1
    recs = parse(get(URL))
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if not recs and OUT.exists(): print("no products parsed – keeping previous", file=sys.stderr); return 0
    OUT.write_text(json.dumps({"fetched": now, "source": URL, "method": "public homepage product teasers; app.bloomwell.de disallowed by robots.txt (not accessed)",
                               "products": recs}, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(recs)} products")
if __name__ == "__main__": sys.exit(main() or 0)
