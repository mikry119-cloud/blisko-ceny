# blisko-ceny

Codziennie aktualizowana baza cen (prices.json) dla aplikacji Blisko.

- Źródło: publiczne strony porównywarek cen (cannapreis.de), z poszanowaniem robots.txt i z opóźnieniami między zapytaniami.
- Aktualizacja: GitHub Actions codziennie ok. 05:23 UTC (`.github/workflows/update.yml`).
- Plik: https://raw.githubusercontent.com/mikry119-cloud/blisko-ceny/main/prices.json

Ceny mają charakter orientacyjny i mogą być nieaktualne. To nie jest porada medyczna.

## PL (od v4)
`update_prices_pl.py` → `prices_pl.json` (ceny „od” za opakowanie z receptamarihuana.pl/lista-lekow, 1 zapytanie dziennie). Osobny workflow `update_pl.yml` – nie dotyka `prices.json` ani geokodowania.
