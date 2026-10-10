#!/usr/bin/env python3
"""Geocode pharmacies listed in prices.json -> pharmacies_geo.json (cache).

Separate from update_prices.py on purpose (do not merge).
- City/address: schema.org JSON-LD (Pharmacy/PostalAddress) on the public cannapreis.de
  pharmacy page (robots.txt allows /apotheke/). 1 request / 2 s.
- Coordinates: OpenStreetMap Nominatim, max 1 request/s, identifying User-Agent,
  results cached forever in pharmacies_geo.json (only new pharmacies are queried).
- pickup: True if the name says 'Abholung' (pickup), otherwise None (= unknown).
"""
import json, re, sys, time, urllib.parse, urllib.request, html as H
UA = "BliskoCeny-geocoder/1.0 (+https://github.com/mikry119-cloud/blisko-ceny)"
OUT = "pharmacies_geo.json"

def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de,en"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def page_address(url):
    t = get(url)
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', t, re.S):
        try: d = json.loads(m.group(1))
        except Exception: continue
        for o in (d if isinstance(d, list) else d.get("@graph", [d])):
            if isinstance(o, dict) and o.get("@type") == "Pharmacy":
                a = o.get("address") or {}
                return {"city": a.get("addressLocality", ""), "street": a.get("streetAddress", ""),
                        "zip": a.get("postalCode", ""), "country": a.get("addressCountry", "DE")}
    return {}

def nominatim(q, cc):
    u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "limit": 1, "countrycodes": cc.lower()})
    time.sleep(1.1)
    r = json.loads(get(u))
    return (float(r[0]["lat"]), float(r[0]["lon"]), r[0].get("display_name", "")) if r else None

def main():
    prices = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "prices.json", encoding="utf-8"))
    try: cache = json.load(open(OUT, encoding="utf-8"))
    except Exception: cache = {"schema": 1, "pharmacies": {}}
    ph = cache.setdefault("pharmacies", {})
    seen = {}
    for p in prices.get("products", []):
        for x in p.get("pharmacies", []):
            if x.get("url"): seen[x["url"]] = x.get("name", "")
    new = 0
    for url, name in sorted(seen.items()):
        if url in ph and ph[url].get("lat") is not None: continue
        e = {"name": name, "url": url, "pickup": True if re.search(r"abhol", name, re.I) else None}
        try:
            time.sleep(2); e.update(page_address(url))
        except Exception as ex: e["error_page"] = str(ex)[:120]
        clean = re.sub(r"\(.*?\)", "", name).strip()
        cc = e.get("country") or "DE"
        tries = []
        if e.get("street"): tries.append(f'{e["street"]}, {e.get("zip","")} {e.get("city","")}')
        if e.get("city"): tries += [f'{clean}, {e["city"]}', e["city"]]
        else:
            m = re.search(r",\s*([^,(]+)", name)  # e.g. "Hirsch Apotheke, Nürnberg"
            if m: tries.append(m.group(1).strip())
        for q in tries:
            try: r = nominatim(q, cc)
            except Exception as ex: e["error_geo"] = str(ex)[:120]; r = None
            if r:
                e.update(lat=r[0], lon=r[1], geo_query=q, geo_display=r[2],
                         precision="address" if q == tries[0] and e.get("street") else ("pharmacy" if clean in q else "city"))
                break
        e["geocoded"] = time.strftime("%Y-%m-%d")
        ph[url] = e; new += 1
        print(("OK " if "lat" in e else "-- ") + name, e.get("city"), e.get("precision"), flush=True)
    cache["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cache["note"] = "Geocoded via OpenStreetMap Nominatim (© OpenStreetMap contributors, ODbL). precision: address|pharmacy|city. pickup: true=pickup mentioned in name, null=unknown."
    json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{new} new/updated, {len(ph)} total")

if __name__ == "__main__":
    main()
