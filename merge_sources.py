#!/usr/bin/env python3
"""Normalize prices.json (cannapreis = pharmacy listings, src 'apteka') and merge bloomwell.json / flowzz.json.
Idempotent: drops previously merged non-apteka records first. Adds to every product:
 src, srcs, cultivar, genetics, thc, cbd, terpenes, irradiated, origin, price_min, price_max, availability, url."""
import json, re, pathlib, datetime
H = pathlib.Path(__file__).parent
P = H / "prices.json"
d = json.loads(P.read_text())
prods = [p for p in d["products"] if p.get("src", "apteka") == "apteka"]
CODE = re.compile(r"^(.*?)\s*\d{1,2}/\d{1,2}\s+(?:[A-Z]{2,4}\s+){0,3}")

def key(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
def cultivar(name):
    m = CODE.match(name or "")
    return name[m.end():].strip() if m and name[m.end():].strip() else name

for p in prods:
    p.pop("offers", None)
    ph = [x.get("price") for x in p.get("pharmacies") or [] if isinstance(x, dict) and x.get("price") is not None]
    base = [v for v in [p.get("price_regular_from"), p.get("price"), p.get("sale_price"), p.get("price_list_min")] if v is not None]
    allp = base + ph
    p.update(src="apteka", srcs=["apteka"], cultivar=p.get("cultivar") or cultivar(p["name"]),
             terpenes=p.get("terpenes") or [], irradiated=p.get("irradiated"), origin=p.get("origin") or "",
             price_min=min(allp) if allp else None, price_max=max(allp) if len(allp) > 1 and max(allp) > min(allp) else None,
             availability="available" if (p.get("price") is not None or ph or p.get("pharmacies_count")) else "unknown")
    if "Unbestrahlt" in p["name"] or "unbestrahlt" in p["name"].lower(): p["irradiated"] = False

idx = {}
for p in prods:
    idx.setdefault(key(p["cultivar"]), []).append(p)

stats, extra, blocked = {"apteka": len(prods)}, [], []
for f, s in [("bloomwell.json", "bloomwell"), ("flowzz.json", "flowzz")]:
    fp = H / f
    if not fp.exists(): continue
    j = json.loads(fp.read_text()); n = dup = 0
    if j.get("blocked"): blocked.append({"name": s, "reason": j["blocked"], "url": j.get("terms_url"), "links": j.get("links", [])})
    for r in j.get("products", []):
        cand = [p for p in idx.get(key(r["cultivar"]), []) if p["type"] == r["type"] and r.get("thc") is not None and p.get("thc") is not None and abs(p["thc"] - r["thc"]) <= 2]
        if cand:  # obvious duplicate: same cultivar, type, THC ±2 -> attach offer
            p = cand[0]; dup += 1
            p.setdefault("offers", []).append({"src": s, "price": r.get("price_min"), "url": r["url"]})
            if s not in p["srcs"]: p["srcs"].append(s)
            pm = r.get("price_min")
            if pm is not None:
                lo = min(x for x in [p["price_min"], pm] if x is not None); hi = max(x for x in [p["price_min"], p["price_max"], pm] if x is not None)
                p["price_min"], p["price_max"] = lo, (hi if hi > lo else None)
        else:
            r = dict(r); r.setdefault("srcs", [s]); r.setdefault("price", r.get("price_min")); r.setdefault("pharmacies", []); r.setdefault("pharmacy", "")
            extra.append(r); n += 1
    stats[s] = {"new": n, "merged_into_existing": dup}

d["products"] = prods + extra
d["merge"] = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "counts": stats, "blocked": blocked}
d["sources"] = [x for x in d.get("sources", []) if x.get("name") not in ("bloomwell.de", "flowzz.com")]
if (H / "bloomwell.json").exists():
    b = json.loads((H / "bloomwell.json").read_text())
    d["sources"].append({"name": "bloomwell.de", "url": b["source"], "method": b["method"], "fetched": b["fetched"]})
d["skipped"] = [x for x in d.get("skipped", []) if x.get("name") != "flowzz.com"]
for b in blocked:
    if b["name"] == "flowzz": d["skipped"].append({"name": "flowzz.com", "url": "https://flowzz.com/agb", "reason": "ToS (AGB §10) forbids scraping/automated access without written permission – link-out only"})
P.write_text(json.dumps(d, ensure_ascii=False, indent=1))
print("merged:", json.dumps(stats), "total", len(d["products"]))
