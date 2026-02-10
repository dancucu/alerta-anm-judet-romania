"""Senzori pentru Alertă ANM Județ România."""
import asyncio
import json
import logging
import os
import re
from datetime import timedelta

import async_timeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_AUTO_DOWNLOAD,
    DEFAULT_SCAN_INTERVAL,
    JUDETE,
)

_LOGGER = logging.getLogger(__name__)

JSON_URL = "https://www.meteoromania.ro/wp-json/meteoapi/v2/avertizari-generale"
HTML_URL = "https://www.meteoromania.ro/avertizari/"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Configurează senzorii pentru integrare."""
    minutes = config_entry.options.get(
        "update_interval",
        config_entry.data.get("update_interval", DEFAULT_SCAN_INTERVAL),
    )
    update_interval = timedelta(minutes=minutes)
    judet_cod = config_entry.data.get("judet_cod", "TM")
    judet_nume = config_entry.data.get("judet_nume", "Timisoara")

    alert_sensor = ANMAlertSensor(hass)
    id_sensor = ANMAlertIDSensor(hass)
    message_sensor = ANMMessageSensor(hass, judet_cod, judet_nume, alert_sensor)
    map_download_sensor = ANMMapDownloadSensor(hass, id_sensor, True)
    map_color_sensor = ANMMapColorSensor(hass, judet_cod, judet_nume, id_sensor)

    entities = [
        alert_sensor,
        id_sensor,
        message_sensor,
        map_download_sensor,
        map_color_sensor,
    ]
    async_add_entities(entities, update_before_add=True)

    async def _periodic_update(now):
        for entity in entities:
            entity.async_schedule_update_ha_state(True)

    async_track_time_interval(hass, _periodic_update, update_interval)
    return True


class ANMAlertSensor(Entity):
    """Senzor pentru lista de avertizări generale ANM."""

    def __init__(self, hass, id_sensor=None):
        self._hass = hass
        self._id_sensor = id_sensor
        self._state = None
        self._attributes = {}
        self._last_success_ts = None
        self._judet_name_to_code = {v.lower(): k for k, v in JUDETE.items()}

    @property
    def name(self):
        return "ANM Avertizare Generala"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def icon(self):
        return "mdi:weather-lightning-rainy"

    @property
    def unique_id(self):
        return "anm_avertizare_generala"

    async def async_update(self, now=None):
        """Actualizează avertizările: JSON primar, HTML fallback, păstrează ultima stare pe erori."""
        prev_state = self._state
        prev_attrs = self._attributes.copy()

        try:
            async with async_timeout.timeout(10):
                session = async_get_clientsession(self._hass, verify_ssl=False)

                # 1) Primar: API JSON
                try:
                    async with session.get(JSON_URL) as response:
                        if response.status == 200:
                            data = await response.json()
                            avertizari = data.get("avertizari", []) if isinstance(data, dict) else []

                            if not avertizari and prev_attrs.get("avertizari"):
                                _LOGGER.warning(
                                    "Răspuns ANM JSON fără avertizări; păstrez ultima stare disponibilă"
                                )
                                self._state = prev_state
                                self._attributes = prev_attrs
                                return

                            # Filtrează NUMAI alertele NATIONAL (informări meteorologice)
                            national_alerts = [a for a in avertizari if a.get("judet") == "NATIONAL"]
                            
                            self._state = "alerta" if national_alerts else "liniste"
                            self._last_success_ts = int(asyncio.get_event_loop().time())
                            
                            # Stochează NUMAI alertele NATIONAL în atribute
                            self._attributes = {
                                "numar_avertizari": len(national_alerts),
                                "avertizari": national_alerts,  # Numai NATIONAL pentru informări generale
                                "friendly_name": "ANM Avertizare Generala",
                                "sursa": "json",
                            }
                            return

                        _LOGGER.warning(
                            "Eroare HTTP %s la API JSON; încerc fallback HTML",
                            response.status,
                        )
                except Exception as exc_json:  # pragma: no cover - runtime log
                    _LOGGER.warning("Eroare la API JSON; încerc fallback HTML: %s", exc_json)

                # 2) Fallback: pagina HTML
                try:
                    async with session.get(HTML_URL) as resp_html:
                        html_ok = resp_html.status == 200
                        html_text = await resp_html.text() if html_ok else ""
                        if html_ok:
                            avertizari = self._parse_html_alerts(html_text)
                            if avertizari or html_text:
                                # Filtrează NUMAI alertele NATIONAL (informări meteorologice)
                                national_alerts = [a for a in avertizari if a.get("judet") == "NATIONAL"]
                                
                                self._state = "alerta" if national_alerts else "liniste"
                                self._last_success_ts = int(asyncio.get_event_loop().time())
                                self._attributes = {
                                    "numar_avertizari": len(national_alerts),
                                    "avertizari": national_alerts,  # Numai NATIONAL pentru informări generale
                                    "friendly_name": "ANM Avertizare Generala",
                                    "sursa": "html",
                                }
                                return
                        _LOGGER.warning(
                            "HTTP %s la /avertizari/; păstrez ultima stare", resp_html.status
                        )
                except Exception as exc_html:  # pragma: no cover - runtime log
                    _LOGGER.warning(
                        "Eroare la parsarea /avertizari/: %s; păstrez ultima stare", exc_html
                    )

                # 3) Ambele au eșuat: păstrăm ultima stare sau unavailable
                if prev_attrs:
                    self._state = prev_state
                    self._attributes = prev_attrs
                else:
                    self._state = "unavailable"
                return
        except Exception as exc:  # pragma: no cover - runtime log
            _LOGGER.warning(
                "Eroare la actualizarea avertizărilor generale; păstrez ultima stare: %s",
                exc,
            )
            if prev_attrs:
                self._state = prev_state
                self._attributes = prev_attrs
            else:
                self._state = "unavailable"

    def _parse_html_alerts(self, html_text):
        """Parsează avertizările din pagina HTML /avertizari/."""
        alerts = []
        if not html_text:
            return alerts

        # Taie tot ce este după Legend (acolo încep nowcasting-urile)
        legend_marker = '<div style="font-weight: bold;width:200px;margin-top:40px">legenda:'
        legend_idx = html_text.lower().find(legend_marker)
        if legend_idx != -1:
            html_text = html_text[:legend_idx]

        parts = []

        def _is_relevant_title(title_text):
            normalized = self._normalize_name(title_text)
            if "nowcasting" in normalized:
                return False
            allowed_keys = (
                "informare meteo",
                "informare meteorologica",
                "atentionare meteo",
                "atentionare meteorologica",
            )
            return any(key in normalized for key in allowed_keys)

        # Caută perechi title+content
        paired_blocks = re.findall(
            r'<div[^>]+alerta_meteo_produsetitle[^>]*>(.*?)</div>\s*<div[^>]+alerta_meteo_produsecontent[^>]*>(.*?)</div>',
            html_text,
            re.S | re.IGNORECASE,
        )
        if paired_blocks:
            for raw_title, body in paired_blocks:
                if _is_relevant_title(raw_title):
                    parts.append(body)

        if not parts:
            split_parts = re.split(r'class="alerta_meteo_produsecontent"', html_text)
            if len(split_parts) > 1:
                parts = split_parts[1:]
            else:
                alt_parts = re.findall(r'<div[^>]+alerta_meteo_produsecontent[^>]*>(.*?)</div>', html_text, re.S)
                if len(alt_parts) > 1:
                    parts = alt_parts
                else:
                    alt_parts = re.findall(r'<div[^>]+alerta[^>]+>(.*?)</div>', html_text, re.S)
                    if alt_parts:
                        parts = alt_parts

        if parts:
            # Elimină explicit blocurile de tip nowcasting (verifică titlul implicit în body)
            # Nu elimina blocuri care doar menționează cuvântul în context
            def _is_nowcasting_block(body_html):
                # Caută "Atenționare nowcasting" sau "Atentionare nowcasting" ca titlu explicit
                return bool(re.search(r'(atentionare|atenționare)\s+nowcasting', body_html, re.IGNORECASE))
            
            parts = [p for p in parts if not _is_nowcasting_block(p)]

        if not parts:
            return alerts

        color_map = {"galben": 1, "portocaliu": 2, "rosu": 3, "informare": 0}
        zone_map = {
            "banat": ["TM", "CS"],
            "sudul banatului": ["TM", "CS"],
            "carpatii meridionali": ["CS", "HD", "GJ", "VL", "AG", "SB", "BV"],
            "extremitatea vestica a carpatilor meridionali": ["CS", "HD", "GJ"],
            "dobrogea": ["CT", "TL"],
            "moldova": ["IS", "VS", "BT", "NT", "BC", "SV", "GL"],
            "transilvania": ["AB", "AR", "BH", "BN", "BV", "CJ", "CV", "HD", "HR", "MM", "MS", "SB", "SJ", "SM"],
            "oltenia": ["DJ", "GJ", "MH", "OT", "VL"],
            "muntenia": ["AG", "BR", "BZ", "CL", "DB", "GR", "IF", "IL", "PH", "TR"]
        }

        for part in parts:
            # Extrage întregul conținut al blocului pentru mesaj
            msg_match = (
                re.search(r"<td[^>]*colspan=[\"']?3[\"']?[^>]*text-align:justify[^>]*>(.*?)</td>", part, re.S)
                or re.search(r"<td[^>]*text-align:justify[^>]*>(.*?)</td>", part, re.S)
                or re.search(r"<td[^>]*colspan=[\"']?3[\"']?[^>]*>(.*?)</td>", part, re.S)
            )
            raw_msg = msg_match.group(1) if msg_match else part
            msg_clean = self._clean_html(raw_msg)
            
            # Împarte mesajul în submesaje dacă conține mai multe coduri
            submessages = self._split_combined_message(msg_clean)
            
            for submsg, subcolor in submessages:
                self._process_single_alert(submsg, subcolor, zone_map, alerts)

        return alerts

    def _split_combined_message(self, msg_clean):
        """Împarte un mesaj combinat în submesaje separate cu codurile lor."""
        # Caută toate blocurile de tip INFORMARE/ATENȚIONARE + COD
        pattern = r'(INFORMARE\s+METEOROLOGIC[AĂ]|ATEN[ȚT]IONARE\s+METEOROLOGIC[AĂ])\s*(.*?)(?=(?:INFORMARE\s+METEOROLOGIC|ATEN[ȚT]IONARE\s+METEOROLOGIC|$))'
        matches = re.findall(pattern, msg_clean, re.IGNORECASE | re.DOTALL)
        
        if not matches:
            # Dacă nu găsim pattern-ul, returnează mesajul întreg
            return [(msg_clean, None)]
        
        result = []
        color_map = {"galben": 1, "portocaliu": 2, "rosu": 3, "informare": 0}
        
        for alert_type, content in matches:
            full_text = alert_type + " " + content
            # Caută COD în acest submesaj
            cod_match = re.search(r"COD\s*:?\s*(GALBEN|PORTOCALIU|ROSU|INFORMARE)", full_text, re.IGNORECASE)
            color_val = color_map.get(cod_match.group(1).lower(), 0) if cod_match else 0
            result.append((full_text.strip(), color_val))
        
        return result if result else [(msg_clean, None)]

    def _process_single_alert(self, msg_clean, color_val, zone_map, alerts):
        """Procesează o singură alertă și adaugă județele afectate."""
        if color_val is None:
            # Determină culoarea din mesaj
            color_map_local = {"galben": 1, "portocaliu": 2, "rosu": 3, "informare": 0}
            color_match = re.search(r"COD\s*:?\s*(GALBEN|PORTOCALIU|ROSU|INFORMARE)", msg_clean, re.IGNORECASE)
            if color_match:
                color_val = color_map_local.get(color_match.group(1).lower(), 0)
            else:
                # Dacă nu găsim COD dar avem INFORMARE în titlu, este informare (cod 0)
                if re.search(r"INFORMARE\s+METEOROLOGIC", msg_clean, re.IGNORECASE):
                    color_val = 0
                else:
                    color_val = 0  # Default la informare
        
        counties = []
        normalized_msg = self._normalize_name(msg_clean)
        
        # Caută județe explicit menționate (cu word boundaries)
        for code, nume in JUDETE.items():
            normalized_county = self._normalize_name(nume)
            # Verifică ca word boundary - nu substring
            pattern = r'\b' + re.escape(normalized_county) + r'\b'
            if re.search(pattern, normalized_msg):
                counties.append(code)
        
        # Dacă nu găsim județe explicit, verificăm zone
        if not counties:
            candidate_codes = []
            for zone_key, zone_codes in zone_map.items():
                if zone_key in normalized_msg:
                    candidate_codes.extend(zone_codes)
            
            # Pentru INFORMARE (cod 0), adaugă ca alertă generală fără județ specific
            # Informările nu se aplică la județe individuale pentru a evita duplicarea
            if color_val == 0:
                alerts.append({
                    "judet": "NATIONAL",  # Marcaj special pentru informări naționale
                    "culoare": color_val,
                    "mesaj": msg_clean,
                })
                # Setăm counties la o listă specială pentru a sări peste distribuția normală
                counties = ["__SKIP__"]
            elif candidate_codes:
                # Pentru cod colorat cu zone multiple menționate, returnăm toți candidații
                # Senzorul de hartă va filtra la nivel de județ
                counties = list(set(candidate_codes))
            else:
                counties = []
        
        # Sărim peste distribuția normală pentru informări
        if counties == ["__SKIP__"]:
            pass  # Informarea deja adăugată mai sus, nu procesăm mai departe
        elif not counties:
            # Aplicăm la toate județele
            for code in JUDETE:
                alerts.append({"judet": code, "culoare": color_val, "mesaj": msg_clean})
        else:
            # Aplicăm doar la județele identificate
            seen = set()
            for county_code in counties:
                if isinstance(county_code, str) and len(county_code) <= 3:
                    code = county_code
                else:
                    # Este nume de județ, trebuie convertit
                    key = county_code.strip().lower()
                    norm_key = self._normalize_name(key)
                    code = self._judet_name_to_code.get(key, self._judet_name_to_code.get(norm_key, county_code))
                
                dedup_key = (code, msg_clean)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                alerts.append({
                    "judet": code,
                    "culoare": color_val,
                    "mesaj": msg_clean,
                })

    def _filter_by_map_sync(self, candidate_codes):
        """Filtrează județele candidate verificând culoarea pe hărțile active (sync)."""
        if not self._id_sensor:
            return candidate_codes
        
        sensor_ids = self._id_sensor.state
        if not sensor_ids or sensor_ids in ["unknown", "unavailable", "0", ""]:
            return candidate_codes
        
        ids_list = [x.strip() for x in str(sensor_ids).split(",") if x.strip()]
        if not ids_list or not candidate_codes:
            return candidate_codes
        
        # Descarcă toate hărțile și verifică fiecare județ
        verified = set()
        session = async_get_clientsession(self._hass, verify_ssl=False)
        
        for map_id in ids_list:
            try:
                # Folosim un loop event existent
                future = self._fetch_and_check_map(session, map_id, candidate_codes)
                colored_counties = self._hass.loop.create_task(future)
                # Colectăm rezultatele în verificare asincronă separată
            except Exception as e:
                _LOGGER.debug(f"Eroare verificare hartă {map_id}: {e}")
        
        # Dacă nu putem verifica, returnăm toți candidații
        return list(candidate_codes)

    async def _fetch_and_check_map(self, session, map_id, candidate_codes):
        """Descarcă harta și verifică care județe sunt colorate."""
        url = f"https://www.meteoromania.ro/wp-content/plugins/meteo/harti/harta.svg.php?id_avertizare={map_id}"
        colored = []
        
        try:
            async with async_timeout.timeout(5):
                async with session.get(url) as response:
                    if response.status != 200:
                        return colored
                    
                    content = await response.text()
                    
                    for judet_cod in candidate_codes:
                        target_id = f'conturJudet{judet_cod}'
                        if target_id not in content:
                            continue
                        
                        # Verifică dacă are fill colorat
                        pattern = rf'{target_id}[^>]*(?:style="[^"]*fill:\s*([^;"]+)|class="([^"]+))'
                        match = re.search(pattern, content)
                        if match:
                            fill_val = (match.group(1) or match.group(2) or "").lower()
                            if any(c in fill_val for c in ['#ffff00', 'rgb(255,255,0)', '#ff6600', '#ff0000', '#b4b4b4', 'galben', 'portocaliu', 'rosu']):
                                colored.append(judet_cod)
                    
                    return colored
        except Exception as e:
            _LOGGER.debug(f"Eroare parsare hartă {map_id}: {e}")
            return colored

    @staticmethod
    def _clean_html(text):
        if not text:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&nbsp;", " ").replace("&ndash;", "-")
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()

    @staticmethod
    def _normalize_name(text):
        if not text:
            return ""
        normalized = text.lower()
        normalized = normalized.replace("ş", "ș").replace("ţ", "ț")
        normalized = normalized.replace("ă", "a").replace("â", "a").replace("î", "i")
        normalized = normalized.replace("ș", "s").replace("ț", "t")
        normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _normalize_alerts(self, alerts):
        """Normalizează alertele; informările fără județ devin naționale (toate județele)."""
        if not isinstance(alerts, list):
            return []

        normalized = []
        for item in alerts:
            if not isinstance(item, dict):
                continue

            msg = item.get("mesaj", "") or item.get("text", "")
            color_raw = item.get("culoare", item.get("cod", 0))
            try:
                color_val = int(color_raw)
            except Exception:  # pragma: no cover - defensive
                color_val = 0

            judete_list = item.get("judete") if isinstance(item.get("judete"), list) else None
            if judete_list:
                for j in judete_list:
                    normalized.append({"judet": j, "culoare": color_val, "mesaj": msg})
                continue

            judet = item.get("judet")
            if judet:
                normalized.append({"judet": judet, "culoare": color_val, "mesaj": msg})
                continue

            # Informare generală fără județe specificate -> replică pe toate județele
            for code in JUDETE:
                normalized.append({"judet": code, "culoare": color_val, "mesaj": msg})

        return normalized


class ANMAlertIDSensor(Entity):
    """Senzor pentru lista de ID-uri de avertizare active."""

    def __init__(self, hass):
        self._hass = hass
        self._state = "0"
        self._attributes = {}

    @property
    def name(self):
        return "ANM Avertizare ID"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def icon(self):
        return "mdi:numeric"

    @property
    def unique_id(self):
        return "anm_avertizare_id"

    async def async_update(self, now=None):
        """Extrage ID-urile de avertizare din pagina HTML ANM."""
        _LOGGER.debug("Actualizare ID-uri Avertizări ANM")
        try:
            async with async_timeout.timeout(10):
                session = async_get_clientsession(self._hass, verify_ssl=False)
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                }
                async with session.get(HTML_URL, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error(
                            "Eroare HTTP %s la preluarea paginii ANM", response.status
                        )
                        return

                    html_content = await response.text()
                    pattern = r"id_avertizare=(\d+)"
                    ids = list(set(re.findall(pattern, html_content)))

                    if ids:
                        ids_sorted = sorted(ids, key=int, reverse=True)
                        self._state = ",".join(ids_sorted)
                        self._attributes = {
                            "id_list": ids_sorted,
                            "numar_id": len(ids_sorted),
                            "friendly_name": "ANM Avertizare ID",
                        }
                        _LOGGER.info("ID-uri ANM găsite: %s", self._state)
                    else:
                        self._state = "0"
                        self._attributes = {
                            "id_list": [],
                            "numar_id": 0,
                            "friendly_name": "ANM Avertizare ID",
                        }
                        _LOGGER.info("Nu s-au găsit ID-uri ANM active")
        except Exception as exc:  # pragma: no cover - runtime log
            _LOGGER.error("Eroare la actualizarea ID-urilor ANM: %s", exc)


class ANMMessageSensor(Entity):
    """Senzor pentru mesajul complet de avertizare pentru județul selectat."""

    def __init__(self, hass, judet_cod, judet_nume, alert_sensor):
        self._hass = hass
        self._judet_cod = judet_cod
        self._judet_nume = judet_nume
        self._alert_sensor = alert_sensor
        self._state = "liniste"
        self._attributes = {
            "tip_cod": "Verde",
            "mesaj_complet": f"Nu sunt avertizări active pentru județul {self._judet_nume}.",
            "friendly_name": f"Mesaj Meteo {self._judet_nume}",
        }

    @property
    def name(self):
        return f"Mesaj Meteo {self._judet_nume}"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def icon(self):
        return "mdi:alert-decagram"

    @property
    def unique_id(self):
        return f"anm_mesaj_meteo_{self._judet_cod.lower()}"

    @property
    def available(self):
        return self._alert_sensor.state not in [None, "unknown", "unavailable"]

    async def async_update(self, now=None):
        await self._process_alerts()

    async def _process_alerts(self):
        """Procesează alertele pentru județul selectat."""
        avertizari = self._alert_sensor.extra_state_attributes.get("avertizari")
        if not avertizari:
            self._state = "liniste"
            self._attributes = {
                "tip_cod": "Verde",
                "mesaj_complet": f"Nu sunt avertizări active pentru județul {self._judet_nume}.",
                "friendly_name": f"Mesaj Meteo {self._judet_nume}",
            }
            return

        if isinstance(avertizari, str):
            self._state = "liniste"
            self._attributes = {
                "tip_cod": "Verde",
                "mesaj_complet": avertizari,
                "friendly_name": f"Mesaj Meteo {self._judet_nume}",
            }
            return

        # Filtrează alertele pentru județul specific + informările naționale
        gl_list = [a for a in avertizari if a.get("judet") == self._judet_cod or a.get("judet") == "NATIONAL"]
        if not gl_list:
            self._state = "liniste"
            self._attributes = {
                "tip_cod": "Verde",
                "mesaj_complet": f"Nu sunt avertizări active pentru județul {self._judet_nume}.",
                "friendly_name": f"Mesaj Meteo {self._judet_nume}",
            }
            return

        self._state = "alerta"
        max_code = max([int(a.get("culoare", 0)) for a in gl_list])
        tip_cod_map = {3: "Rosu", 2: "Portocaliu", 1: "Galben", 0: "Verde"}
        tip_cod = tip_cod_map.get(max_code, "Verde")

        mesaje = []
        for item in gl_list:
            msg_raw = item.get("mesaj", "")
            msg_raw = msg_raw.replace("<br />", "\n").replace("</p>", "\n")
            msg_raw = re.sub(r"<[^>]*>", "", msg_raw)
            msg_raw = msg_raw.replace("&nbsp;", " ").replace("&ndash;", "-").strip()

            cod = int(item.get("culoare", 0))
            if cod == 1:
                msg_raw = re.sub(r"COD PORTOCALIU[\s\S]*?(?=COD|$)", "", msg_raw, flags=re.IGNORECASE)
                msg_raw = re.sub(r"COD RO[SȘ]U[\s\S]*?(?=COD|$)", "", msg_raw, flags=re.IGNORECASE)
            elif cod == 2:
                msg_raw = re.sub(r"COD GALBEN[\s\S]*?(?=COD|$)", "", msg_raw, flags=re.IGNORECASE)
                msg_raw = re.sub(r"COD RO[SȘ]U[\s\S]*?(?=COD|$)", "", msg_raw, flags=re.IGNORECASE)
            elif cod == 3:
                msg_raw = re.sub(r"COD GALBEN[\s\S]*?(?=COD|$)", "", msg_raw, flags=re.IGNORECASE)
                msg_raw = re.sub(r"COD PORTOCALIU[\s\S]*?(?=COD|$)", "", msg_raw, flags=re.IGNORECASE)

            msg_final = re.sub(r"\n\s*\n", "\n\n", msg_raw).strip()
            mesaje.append(msg_final)

        mesaj_complet = "\n\n".join(mesaje).strip()
        self._attributes = {
            "tip_cod": tip_cod,
            "mesaj_complet": mesaj_complet
            if mesaj_complet
            else f"Nu sunt avertizări active pentru județul {self._judet_nume}.",
            "friendly_name": f"Mesaj Meteo {self._judet_nume}",
        }

        _LOGGER.info(
            "Mesaj meteo actualizat pentru %s: %s (%s)",
            self._judet_nume,
            self._state,
            tip_cod,
        )


class ANMMapDownloadSensor(Entity):
    """Senzor care descarcă automat hărțile ANM în /config/www/."""

    def __init__(self, hass, id_sensor, auto_download=True):
        self._hass = hass
        self._id_sensor = id_sensor
        self._auto_download = auto_download
        self._state = "idle"
        self._attributes = {
            "friendly_name": "Descărcare Hărți ANM",
            "descarcari_reusite": [],
            "descarcari_esuate": [],
        }

    @property
    def name(self):
        return "Descărcare Hărți ANM"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def icon(self):
        return "mdi:download"

    @property
    def unique_id(self):
        return "anm_descarcare_harti"

    async def async_update(self, now=None):
        sensor_ids = self._id_sensor.state
        if not sensor_ids or sensor_ids in ["unknown", "unavailable", "0", ""]:
            self._state = "idle"
            self._attributes.update({
                "ids_detectate": sensor_ids if sensor_ids else "0",
                "descarcari_reusite": [],
                "descarcari_esuate": [],
            })
            return

        ids_list = [x.strip() for x in sensor_ids.split(",") if x.strip()]
        if not ids_list:
            self._state = "idle"
            self._attributes.update({
                "ids_detectate": sensor_ids,
                "descarcari_reusite": [],
                "descarcari_esuate": [],
            })
            return

        target_dir = self._hass.config.path("www")
        os.makedirs(target_dir, exist_ok=True)

        succes = []
        esuate = []

        session = async_get_clientsession(self._hass, verify_ssl=False)

        for map_id in ids_list:
            url = (
                "https://www.meteoromania.ro/wp-content/plugins/meteo/harti/"
                f"harta.svg.php?id_avertizare={map_id}"
            )
            filename = os.path.join(target_dir, f"harta_anm_{map_id}.svg")

            try:
                async with async_timeout.timeout(10):
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            esuate.append({"id": map_id, "status": resp.status})
                            continue
                        content = await resp.read()

                def _write_file(path, data):
                    with open(path, "wb") as file_handle:
                        file_handle.write(data)

                await self._hass.async_add_executor_job(_write_file, filename, content)
                succes.append(filename)
            except Exception as exc:  # pragma: no cover - runtime log
                esuate.append({"id": map_id, "eroare": str(exc)})

        self._state = len(succes)
        self._attributes.update({
            "ids_detectate": ids_list,
            "descarcari_reusite": succes,
            "descarcari_esuate": esuate,
            "folder": target_dir,
            "friendly_name": "Descărcare Hărți ANM",
        })


class ANMMapColorSensor(Entity):
    """Senzor pentru culoarea județului pe hartă."""

    def __init__(self, hass, judet_cod, judet_nume, id_sensor):
        self._hass = hass
        self._judet_cod = judet_cod
        self._judet_nume = judet_nume
        self._id_sensor = id_sensor
        self._state = "verde"
        self._attributes = {}
        self._entity_picture = None

    @property
    def name(self):
        return f"Culoare Hartă {self._judet_nume}"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def icon(self):
        if self._state == "rosu":
            return "mdi:alert-octagon"
        if self._state == "portocaliu":
            return "mdi:alert"
        if self._state == "galben":
            return "mdi:alert-circle"
        if self._state == "informare":
            return "mdi:information"
        return "mdi:check-circle"

    @property
    def unique_id(self):
        return f"anm_culoare_harta_{self._judet_cod.lower()}"

    @property
    def entity_picture(self):
        """Returnează URL-ul hărții cu prioritate cea mai mare."""
        return self._entity_picture
        max_priority = 0
        max_id = None
        
        for map_id, color in date_harti.items():
            if priority.get(color, 0) > max_priority:
                max_priority = priority.get(color, 0)
                max_id = map_id
        
        # Returnează URL-ul local al hărții (informare inclusă)
        if max_id and max_priority > 0:
            return f"/local/harta_anm_{max_id}.svg"
        
        return None

    async def async_update(self, now=None):
        """Actualizare culoare prin apelarea scriptului check_map.py."""
        sensor_ids = self._id_sensor.state

        if not sensor_ids or sensor_ids in ["unknown", "unavailable", "0", ""]:
            self._state = "verde"
            self._entity_picture = None
            self._attributes = {
                "date_harti": {},
                "judet_cod": self._judet_cod,
                "friendly_name": f"Culoare Hartă {self._judet_nume}",
            }
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "check_map.py")

        try:
            process = await asyncio.create_subprocess_exec(
                "python3",
                script_path,
                sensor_ids,
                self._judet_cod,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                result = json.loads(stdout.decode())
                date_harti = result.get("date_harti", {})
                
                _LOGGER.info(
                    "check_map.py output pentru %s: %s", 
                    self._judet_nume, date_harti
                )

                priority = {"rosu": 4, "portocaliu": 3, "galben": 2, "informare": 1, "verde": 0}
                max_color = "verde"
                max_priority = 0
                max_id = None

                for map_id, color in date_harti.items():
                    if priority.get(color, 0) > max_priority:
                        max_priority = priority.get(color, 0)
                        max_color = color
                        max_id = map_id

                self._state = max_color
                
                # Setează entity_picture pentru culori non-verde (inclusiv informare)
                if max_id and max_priority > 0:
                    self._entity_picture = f"/local/harta_anm_{max_id}.svg"
                else:
                    self._entity_picture = None
                
                self._attributes = {
                    "date_harti": date_harti,
                    "numar_harti_verificate": len(date_harti),
                    "judet_cod": self._judet_cod,
                    "friendly_name": f"Culoare Hartă {self._judet_nume}",
                }
                
                # Adaugă URL-ul hărții în atribute pentru referință
                if self._entity_picture:
                    self._attributes["entity_picture"] = self._entity_picture

                _LOGGER.info(
                    "Culoare hartă pentru %s: %s (harta: %s)", 
                    self._judet_nume, self._state, self._entity_picture
                )
            else:
                _LOGGER.error("Eroare la rularea check_map.py: %s", stderr.decode())
                self._state = "necunoscut"
                self._entity_picture = None

        except Exception as exc:  # pragma: no cover - runtime log
            _LOGGER.error("Eroare la verificarea culorii hărții: %s", exc)
            self._state = "necunoscut"
            self._entity_picture = None
