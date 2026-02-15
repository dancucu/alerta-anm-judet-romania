import json
import re

# Citește fișierul .anm_alert_cache.json
with open(".anm_alert_cache.json", "r", encoding="utf-8") as f:
    cache = json.load(f)

raw = cache.get("api_raw", {}).get("raw", {})



# Extrage avertizările din structura raw
avertizari = []
if raw and "avertizare" in raw and raw["avertizare"]:
    for idx, av in enumerate(raw["avertizare"]):
        print(f"DEBUG avertizare[{idx}]: {json.dumps(av, ensure_ascii=False, indent=2)[:1000]}")  # print first 1000 chars
        attrs = av.get("@attributes", {})
        judete = []
        # 1. Extrage din subsecțiunea 'judet' dacă există
        if "judet" in av:
            judet_data = av["judet"]
            if isinstance(judet_data, dict):
                judet_data = [judet_data]
            for j in judet_data:
                jattrs = j.get("@attributes", {})
                cod = jattrs.get("cod")
                culoare = int(jattrs.get("culoare", 0))
                msg = attrs.get("numeTipMesaj", "") + ": " + re.sub(r'<[^>]+>', '', attrs.get("mesaj", "")).replace("\n", " ").strip()
                if cod:
                    judete.append({
                        "judet": cod,
                        "culoare": culoare,
                        "mesaj": msg
                    })
        # 2. Extrage din @attributes dacă există cod (inclusiv coordGis)
        if ("cod" in attrs) and ("coordGis" in attrs or "culoare" in attrs):
            cod = attrs.get("cod")
            culoare = int(attrs.get("culoare", 0))
            msg = attrs.get("numeTipMesaj", "") + ": " + re.sub(r'<[^>]+>', '', attrs.get("mesaj", "")).replace("\n", " ").strip()
            judete.append({
                "judet": cod,
                "culoare": culoare,
                "mesaj": msg
            })
        # 3. Dacă nu există niciuna din cele de mai sus, pune ca informare națională
        if not judete:
            msg = attrs.get("numeTipMesaj", "") + ": " + re.sub(r'<[^>]+>', '', attrs.get("mesaj", "")).replace("\n", " ").strip()
            judete.append({
                "judet": "NATIONAL",
                "culoare": int(attrs.get("culoare", 0)),
                "mesaj": msg
            })
        avertizari.extend(judete)
        # Debug: afișează codurile județelor extrase pentru fiecare avertizare
        print(f"Avertizare: {attrs.get('numeTipMesaj', '')}, Judete extrase: {[j['judet'] for j in judete]}")


cache["alert_state"] = "alerta" if avertizari else "liniste"
cache["alert_attrs"] = {
    "numar_avertizari": len(avertizari),
    "avertizari": avertizari,
    "friendly_name": "Avertizari Meteo ANM",
    "sursa": "cache",
    "sursa_activa": "cache",
    # Expune datele brute pentru Home Assistant
    "api_raw": raw,
    "avertizari_raw": raw.get("avertizare", [])
}

with open(".anm_alert_cache.json", "w", encoding="utf-8") as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"Generat alert_attrs cu {len(avertizari)} avertizari din api_raw.")
print(f"Lista coduri judete extrase: {[j['judet'] for j in avertizari]}")
