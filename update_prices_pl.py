#!/usr/bin/env python3
"""Daily PL medical cannabis 'from' prices -> prices_pl.json.
Source: receptamarihuana.pl/lista-lekow (public list, robots.txt allows all; 1 request/day).
Prices are the lowest pharmacy package price ('od') per variety; not per-pharmacy prices.
Separate from update_prices.py (DE) on purpose: failure here never touches prices.json."""
import re, json, sys, html, datetime, urllib.request, pathlib
URL = 'https://receptamarihuana.pl/lista-lekow/'
UA = 'BliskoPriceBot/1.0 (+https://github.com/mikry119-cloud/blisko-ceny)'
OUT = pathlib.Path(__file__).parent / 'prices_pl.json'

def num(s):
    return float(s.replace('\xa0', '').replace(' ', '').replace(',', '.')) if s else None

def main():
    req = urllib.request.Request(URL, headers={'User-Agent': UA})
    s = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
    # section headings determine type
    parts = re.split(r'<h2[^>]*>', s)
    prods = []
    for part in parts:
        head = re.sub('<[^>]+>', '', part[:400]).lower()
        typ = 'extract' if ('ekstrakt' in head or 'olej' in head) else 'flower'
        for b in re.findall(r'<div class="rm-drug"[^>]*>(.*?)</div>\s*</div>\s*(?=<div class="rm-drug"|</div>)', part, re.S):
            g = lambda p: (re.search(p, b, re.S) or [None, None])[1]
            name = html.unescape(re.sub('<[^>]+>', '', g(r'class="dtitle"[^>]*>(.*?)</a>') or '')).strip()
            if not name:
                continue
            thc = g(r'THC\s*([\d,\.]+)\s*%'); cbd = g(r'CBD\s*([<≤]?\s*[\d,\.]+)\s*%')
            ppg = g(r'class="price">\s*od\s*<b>([\d,\.\s]+)</b>')
            pk = g(r'opak\.\s*([\d,\.]+)\s*(g|ml)'); pkp = g(r'od\s*([\d\s,\.]+)\s*zł</div>')
            unit = (re.search(r'opak\.\s*[\d,\.]+\s*(g|ml)', b) or [None, 'g'])[1]
            av = g(r'dostępny w\s*(\d+)%')
            pack = num(pk) if pk else None; packp = num(pkp) if pkp else None
            ppu = round(packp / pack, 2) if pack and packp else num(ppg)
            prods.append({'name': name, 'type': typ, 'thc': num(thc), 'cbd_text': (cbd or '').replace(' ', ''),
                          'price': ppu, 'unit': unit, 'pack': pack, 'pack_price_from': packp,
                          'availability_pct': int(av) if av else None,
                          'url': g(r'class="dmore" href="([^"]+)"') or URL,
                          'pharmacies_url': g(r'class="gp" href="([^"]+)"')})
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    d = {'schema': 1, 'country': 'PL', 'currency': 'PLN', 'updated': now,
         'disclaimer': "Ceny 'od' = najniższa cena opakowania w aptekach wg źródła; nie jest to cena konkretnej apteki. Tylko na receptę. Zadzwoń do apteki przed wizytą.",
         'sources': [{'name': 'receptamarihuana.pl', 'url': URL, 'method': 'public HTML, 1 req/day, robots.txt allows', 'fetched': now},
                     {'name': 'gdziepolek.pl (linki do aptek)', 'url': 'https://www.gdziepolek.pl/', 'method': 'link only, not scraped'}],
         'products': prods}
    if len(prods) < 5:
        print('too few products', len(prods)); sys.exit(1)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    print('PL products:', len(prods))

if __name__ == '__main__':
    main()
