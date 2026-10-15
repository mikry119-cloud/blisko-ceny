#!/usr/bin/env python3
"""flowzz.com – NOT scraped (ToS forbids it).

Checked 2026-10-15: robots.txt allows / (except /account), and the site exposes a JSON API
(/api/v1/views/flowers|extracts, Strapi pagination), BUT the AGB section 10
"Verbot von automatisiertem Zugriff und Datenerhebung" explicitly prohibits scraping/crawling,
bots/scripts and automated data collection without written permission from Flowzz
(https://flowzz.com/agb). We respect that: this script makes NO requests and only writes
flowzz.json with the block reason + manual link-outs for users (no product data).
If written permission/API access from Flowzz is obtained, implement fetching here.
"""
import json, pathlib, datetime
OUT = pathlib.Path(__file__).parent / "flowzz.json"
LINKS = [("Wszystkie produkty", "https://flowzz.com/product"),
         ("Kwiaty", "https://flowzz.com/medizinische-cannabisblueten"),
         ("Ekstrakty", "https://flowzz.com/extract")]
OUT.write_text(json.dumps({
    "checked": datetime.date.today().isoformat(), "products": [],
    "blocked": "AGB §10 flowzz.com zabrania scrapingu/automatycznego pobierania danych bez pisemnej zgody – dane nie są pobierane",
    "terms_url": "https://flowzz.com/agb",
    "links": [{"name": n, "url": u} for n, u in LINKS]}, ensure_ascii=False, indent=1))
print("flowzz: blocked by ToS – wrote link-outs only ->", OUT)
