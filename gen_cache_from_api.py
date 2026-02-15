#!/usr/bin/env python3
"""
Script pentru a genera .anm_alert_cache.json dintr-un fișier de răspuns API ANM.
Utilizare:
    python3 gen_cache_from_api.py api_response.json .anm_alert_cache.json
"""
import json
import sys
import os

# JUDETE coduri (copiat din const.py, dacă nu există import direct)
JUDETE = {
    "AB": "Alba", "AR": "Arad", "AG": "Argeș", "BC": "Bacău", "BH": "Bihor", "BN": "Bistrița-Năsăud", "BR": "Brăila", "BT": "Botoșani", "BV": "Brașov", "BZ": "Buzău", "CS": "Caraș-Severin", "CL": "Călărași", "CJ": "Cluj", "CT": "Constanța", "CV": "Covasna", "DB": "Dâmbovița", "DJ": "Dolj", "GL": "Galați", "GR": "Giurgiu", "GJ": "Gorj", "HR": "Harghita", "HD": "Hunedoara", "IL": "Ialomița", "IS": "Iași", "IF": "Ilfov", "MM": "Maramureș", "MH": "Mehedinți", "MS": "Mureș", "NT": "Neamț", "OT": "Olt", "PH": "Prahova", "SM": "Satu Mare", "SJ": "Sălaj", "SB": "Sibiu", "SV": "Suceava", "TR": "Teleorman", "TM": "Timiș", "TL": "Tulcea", "VS": "Vaslui", "VL": "Vâlcea", "VN": "Vrancea", "B": "București"
}

def normalize_alerts(alerts):
    """
    Normalizează alertele din structura API ANM (cheie 'avertizare') pentru cache.
    """
    if not isinstance(alerts, list):
        return []
    normalized = []
    for item in alerts:
        if not isinstance(item, dict):
            continue
        attr = item.get("@attributes", {})
        msg = attr.get("mesaj", "") or item.get("mesaj", "")
        color_raw = attr.get("culoare", 0)
        try:
            color_val = int(color_raw)
        except Exception:
            color_val = 0
        judete = item.get("judet")
        # Caz 1: lista de județe (item['judet'] este listă de dict cu '@attributes')
        if isinstance(judete, list):
            for j in judete:
                if isinstance(j, dict) and "@attributes" in j:
                    cod = j["@attributes"].get("cod")
                    culoare_j = j["@attributes"].get("culoare", color_val)
                    try:
                        culoare_j = int(culoare_j)
                    except Exception:
                        culoare_j = color_val
                    if cod:
                        normalized.append({"judet": cod, "culoare": culoare_j, "mesaj": msg})
            continue
        # Caz 2: un singur județ (dict cu '@attributes')
        if isinstance(judete, dict) and "@attributes" in judete:
            cod = judete["@attributes"].get("cod")
            culoare_j = judete["@attributes"].get("culoare", color_val)
            try:
                culoare_j = int(culoare_j)
            except Exception:
                culoare_j = color_val
            if cod:
                normalized.append({"judet": cod, "culoare": culoare_j, "mesaj": msg})
            continue
        # Caz 3: informare generală fără județe sau cu judet gol -> replică pe toate județele
        if not judete or (isinstance(judete, list) and len(judete) == 0):
            for code in JUDETE:
                normalized.append({"judet": code, "culoare": color_val, "mesaj": msg})
    return normalized

def main():
    if len(sys.argv) < 3:
        print("Utilizare: python3 gen_cache_from_api.py api_response.json .anm_alert_cache.json")
        sys.exit(1)
    api_file = sys.argv[1]
    cache_file = sys.argv[2]
    with open(api_file, "r", encoding="utf-8") as f:
        api_data = json.load(f)
    # Acceptă atât 'avertizari' cât și 'avertizare' ca listă de alerte
    if isinstance(api_data, dict):
        alerts_raw = api_data.get("avertizari")
        if alerts_raw is None:
            alerts_raw = api_data.get("avertizare", [])
    else:
        alerts_raw = []

    # Detectează structura modernă (listă de dict cu cheile 'judet', 'culoare', 'mesaj')
    def is_modern_alerts(alerts):
        if not isinstance(alerts, list):
            return False
        for item in alerts:
            if not isinstance(item, dict):
                return False
            if not all(k in item for k in ("judet", "culoare", "mesaj")):
                return False
        return True

    if is_modern_alerts(alerts_raw):
        alerts = alerts_raw
    else:
        alerts = normalize_alerts(alerts_raw)

    alert_state = "alerta" if alerts else "liniste"
    alert_attrs = {
        "numar_avertizari": len(alerts),
        "avertizari": alerts,
        "friendly_name": "Avertizari Meteo ANM",
        "sursa": "json",
        "sursa_activa": "json"
    }
    cache_data = {
        "alert_state": alert_state,
        "alert_attrs": alert_attrs,
        "api_raw": api_data
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    print(f"Cache salvat: {cache_file} ({len(alerts)} avertizari)")
