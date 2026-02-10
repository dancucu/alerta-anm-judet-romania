# Changelog

## 1.1.3 - 2026-02-10
- Fallback HTML mai tolerant: detectează alertele chiar dacă structura de pe /avertizari/ are clase/TD-uri diferite; suportă culoarea "INFORMARE".

## 1.1.2 - 2026-02-10
- Informările fără județe sau cod (ex. „toată țara”) se aplică automat tuturor județelor și apar în senzorii de mesaj.
- Tipul 0 este etichetat ca „Informare” în `sensor.mesaj_meteo_{judet}`.

## 1.1.1 - 2026-02-10
- Renamed `sensor.anm_avertizare_generala` to `sensor.avertizari_meteo_anm` (breaking: entity_id changes; reselect in dashboards/automations).

## 1.1.0 - 2026-02-09
- Fallback to ANM HTML page when the JSON API is empty or unavailable, keeping the last valid alert state.
- Automatic download of active alert SVG maps to `/config/www`, with success/error tracking.
- Map color detection from downloaded SVGs, exposing county color via the color sensor.
- Refreshed Lovelace card snippet and helper automation for map downloads; updated manifest docs link.

## 1.0.8
- Added GitHub badges to the README.
