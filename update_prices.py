#!/usr/bin/env python3
"""Blisko – medical-cannabis price DB updater (Germany).

Fetches PUBLIC listing pages only, honours robots.txt (urllib.robotparser) and a
polite delay, no login, no captcha/JS-challenge bypass.  Output:
prices.json next to this script.

Sources (see SOURCES / SKIPPED below):
  * cannapreis.de  – HTML listing pages /shop/blueten/ & /shop/extrakte/ (?p= pagination
    explicitly allowed in robots.txt) + product pages /shop/preis/<slug>/ for the
    per-pharmacy table.  Its /api/v1/ is Disallowed in robots.txt -> NOT used.
Usage: python3 update_prices.py [--pages-flower 6] [--pages-extract 3] [--details 80]
"""
import argparse, datetime as dt, html, json, re, sys, time, urllib.request, urllib.robotparser
from pathlib import Path

UA = "BliskoPriceBot/1.0 (+private non-commercial price overview; respects robots.txt)"
DELAY = 1.5
OUT = Path(__file__).with_name("prices.json")
BASE = "https://cannapreis.de"

SKIPPED = [
    {"name": "grammpreis.de", "url": "https://grammpreis.de/", "reason": "JS browser check on listing pages; site explicitly asks to use its partner API instead of scraping"},
    {"name": "hanfvergleich.de", "url": "https://hanfvergleich.de/cannabis-preisindex", "reason": "Vercel Security Checkpoint (bot challenge) – no bypass"},
    {"name": "cannavergleich.com", "url": "https://cannavergleich.com/", "reason": "data is mirrored from cannapreis.de (duplicate); /api/ disallowed"},
    {"name": "cannapreis.de /api/v1/", "url": "https://cannapreis.de/api/v1/markt", "reason": "documented as public API but Disallowed in robots.txt -> not used"},
    {"name": "Shop Apotheke", "url": "https://www.shop-apotheke.com/", "reason": "general online pharmacy; no public cannabis-flower price list found"},
]

# Promotions published by the portals themselves (checked manually 2026-10-10; no codes).
PORTAL_PROMOS = [
    {"portal": "Bloomwell", "text": "Rezeptanfrage 25,22 € – Aktion: gratis (limitierte Produktauswahl)", "code": None,
     "source_url": "https://bloomwell.de/kosten-rechnungen-kostenubernahme", "seen": "2026-10-10", "verified": True},
    {"portal": "Dr. Ansay", "text": "Rezept 'ab 0 €' / ab 14,20 € (laut Website)", "code": None,
     "source_url": "https://dransay.com/cannabis-rezept-online", "seen": "2026-10-10", "verified": True},
    {"portal": "CanDoc", "text": "Cannabis-Rezept online 'ab 0 €'", "code": None,
     "source_url": "https://can-doc.de/", "seen": "2026-10-10", "verified": True},
]


# Prescription / telemedicine fees (researched 2026-10-10). "check" regex is re-verified on the public page
# by the scraper (robots.txt respected); if found, "checked" is set to today, else the static value is kept.
PORTALS = [
    {"id": "ansay", "name": "Dr. Ansay", "fee": 14.20, "fee_note": "Folgerezept 14,20 €; Erstrezept dla nowych pacjentów 'ab 0 €'",
     "source_url": "https://dransay.com/cannabis-rezept-online", "seen": "2026-10-10", "check": r"14,20\s*€"},
    {"id": "bloomwell", "name": "Bloomwell", "fee": 25.22, "fee_note": "Rezeptanfrage 25,22 € (GOÄ); Folgerezept ~28,25 €; akcja: gratis (ograniczony wybór)",
     "source_url": "https://bloomwell.de/kosten-rechnungen-kostenubernahme", "seen": "2026-10-10", "check": r"25,22\s*€"},
    {"id": "candoc", "name": "CanDoc", "fee": 0.0, "fee_note": "Fragebogen 'ab 0 €'; Videosprechstunde 35 €",
     "source_url": "https://can-doc.de/pages/preise", "seen": "2026-10-10", "check": r"35\s*€"},
    {"id": "cannaleo", "name": "Cannaleo (Rezeptkonfigurator)", "fee": 7.99, "fee_note": "Konfigurator kostenlos; opłatę pobiera partner telemedyczny (np. DoktorABC ~7,99 € wg relacji użytkownika – niezweryfikowane)",
     "source_url": "https://cannaleo.de/rezeptkonfigurator/faq", "seen": "2026-10-10", "verified": False},
]
# Shipping fees per pharmacy (public info). match = case-insensitive substring of pharmacy name. Others: unknown.
SHIPPING = [
    {"match": "schloss-apotheke", "fee": 7.95, "free_from": 150.0, "note": "svapo.de: 7,95 €, gratis od 150 € (GKV zawsze gratis)",
     "source_url": "https://www.svapo.de/faq/", "seen": "2026-10-10"},
    {"match": "svapo", "fee": 7.95, "free_from": 150.0, "note": "svapo.de: 7,95 €, gratis od 150 €", "source_url": "https://www.svapo.de/faq/", "seen": "2026-10-10"},
    {"match": "kraut kurier", "fee": 0.0, "free_from": None, "note": "'Kostenloser Versand' wg profilu na nordleaf.de (źródło pośrednie)",
     "source_url": "https://nordleaf.de/pages/apotheke/linden-apotheke", "seen": "2026-10-10"},
]

def check_portals(today):
    out = []
    for p in PORTALS:
        q = {k: v for k, v in p.items() if k != "check"}
        if "check" in p:
            page = get(p["source_url"])
            q.setdefault("verified", True)  # manually researched on "seen" date
            q["auto_checked"] = bool(page and re.search(p["check"], txt(page)))  # False also when robots.txt disallows
            if q["auto_checked"]: q["checked"] = today
        out.append(q)
    return out

_rp = {}
def allowed(url):
    host = re.match(r"https?://[^/]+", url).group(0)
    if host not in _rp:
        rp = urllib.robotparser.RobotFileParser(host + "/robots.txt"); rp.read(); _rp[host] = rp
    return _rp[host].can_fetch(UA, url)

def get(url):
    if not allowed(url):
        print("robots.txt disallows", url, file=sys.stderr); return None
    time.sleep(DELAY)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        print("ERR", url, e, file=sys.stderr); return None

txt = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
num = lambda s: float(s.replace(".", "").replace(",", ".")) if s else None

CARD = re.compile(r'<div class="cp-product-card".*?(?=<div class="cp-product-card"|<nav|</section|<div class="cp-pag)', re.S)
def parse_list(page, ptype):
    out = []
    for c in CARD.findall(page):
        m = re.search(r'href="(https://cannapreis\.de/shop/preis/[^"]+)"', c)
        title = re.search(r'cp-card-title">(.*?)</div>', c, re.S)
        if not (m and title): continue
        sub = txt((re.search(r'cp-card-sub">(.*?)</div>', c, re.S) or [None, ""])[1])
        prod = re.search(r'cp-card-sub">.*?</div>\s*<div[^>]*>(.*?)</div>', c, re.S)
        price = re.search(r'cp-card-price">\s*ab\s*([\d.,]+)\s*€(?:/(\w+))?', c)
        sale = re.search(r'SALE!\s*(\d+)\s*Apos?\s*für\s*([\d.,]+)\s*€', c)
        thc = re.search(r'([\d,]+)%\s*THC', sub); cbd = re.search(r'([\d,]+)%\s*CBD', sub)
        gen = sub.split("•")[0].strip() if "•" in sub else ""
        p = num(price.group(1)) if price else None
        best = num(sale.group(2)) if sale else p
        out.append({"name": txt(title.group(1)), "producer": txt(prod.group(1)) if prod else "",
            "type": ptype, "genetics": gen if gen in ("Sativa", "Indica", "Hybrid") else "",
            "thc": num(thc.group(1)) if thc else None, "cbd": num(cbd.group(1)) if cbd else None,
            "price": best, "unit": (price.group(2) if price and price.group(2) else "g"),
            "price_regular_from": p, "promo": bool(sale),
            "promo_text": f"SALE: {sale.group(1)} Apotheke(n) für {sale.group(2)} €" if sale else "",
            "pharmacy": "", "pharmacies": [], "url": m.group(1), "source": "cannapreis.de"})
    return out

ROW = re.compile(r'<a href="(https://cannapreis\.de/apotheke/[^"]+)" class="pnp-alist">.*?pnp-aname">(.*?)</div>.*?(?:pnp-acity">(.*?)</div>)?.*?pnp-astand"[^>]*>(.*?)</div>.*?pnp-aprice">([\d.,]+)\s*€', re.S)
def parse_detail(page, item):
    rows = ROW.findall(page)[:3]
    item["pharmacies"] = [{"name": txt(n), "city": txt(c or ""), "price": num(p), "stand": txt(s).replace("Preis vor", "vor"), "url": u} for u, n, c, s, p in rows]
    if rows:
        item["pharmacy"] = item["pharmacies"][0]["name"]; item["price"] = item["pharmacies"][0]["price"]
    avg = re.search(r'([\d.,]+)\s*€/g\s*Durchschnitt', txt(page))
    if avg: item["avg_price"] = num(avg.group(1))

def find_codes(page, url, today):
    codes = []
    for m in re.finditer(r'Code\s+<?[^A-Z0-9]{0,40}([A-Z0-9]{5,20})\b(.{0,120})', txt(page)):
        code, ctx = m.group(1), m.group(2)
        if any(c["code"] == code for c in codes): continue
        codes.append({"code": code, "text": re.split(r"\s\d\d Std|×", txt("Nutze den Code " + code + ctx))[0][:140], "issuer": "cannapreis.de (listing site banner)",
            "source_url": url, "seen": today, "verified": False,
            "note": "Published by price-comparison site, not by the pharmacy/portal itself – unverified."})
    return codes

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--pages-flower", type=int, default=6)
    ap.add_argument("--pages-extract", type=int, default=3); ap.add_argument("--details", type=int, default=80)
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc); today = dt.datetime.now().date().isoformat()  # box-local date
    items, codes = {}, []
    for path, ptype, pages in (("/shop/blueten/", "flower", a.pages_flower), ("/shop/extrakte/", "extract", a.pages_extract)):
        for p in range(1, pages + 1):
            url = f"{BASE}{path}" + (f"?p={p}" if p > 1 else "")
            page = get(url)
            if not page: break
            if p == 1 and not codes: codes = find_codes(page, url, today)
            got = parse_list(page, ptype); print(url, len(got))
            if not got: break
            for it in got: items.setdefault(it["url"], it)
    lst = sorted(items.values(), key=lambda x: (x["price"] or 1e9))
    for it in lst[: a.details]:
        page = get(it["url"])
        if page: parse_detail(page, it)
    lst.sort(key=lambda x: (x["price"] or 1e9))
    portals = check_portals(today)
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    data = {"schema": 1, "updated": now.isoformat(timespec="seconds"), "currency": "EUR", "country": "DE",
        "disclaimer": "Prices from public comparison listings; may be outdated. Medical cannabis in Germany only with a doctor's prescription (MedCanG). Not medical advice.",
        "sources": [{"name": "cannapreis.de", "url": BASE + "/", "method": "public HTML listing + product pages, robots.txt respected", "fetched": now.isoformat(timespec="seconds")}],
        "skipped": SKIPPED, "codes": codes or prev.get("codes", []), "promotions_portals": PORTAL_PROMOS,
        "portals": portals, "shipping": SHIPPING, "shipping_default": {"fee": None, "note": "nieznane – sprawdź w aptece"},
        "products": lst}
    if not lst and prev.get("products"):
        print("No products fetched – keeping previous file", file=sys.stderr); return 1
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(lst)} products, {len(codes)} codes")

if __name__ == "__main__":
    sys.exit(main())
