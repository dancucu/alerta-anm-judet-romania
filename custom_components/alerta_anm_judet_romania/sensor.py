"""Senzori pentru Alertă ANM Județ România."""
import asyncio
import json
import logging
import os
import re
from datetime import timedelta


# Importuri Home Assistant – ignoră erorile de import la rulare locală
try:
    import async_timeout
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.event import async_track_time_interval
except ImportError:
    # Pentru testare/analiză statică în afara Home Assistant
    async_timeout = None
    async_get_clientsession = None
    Entity = object
    def async_track_time_interval(*a, **kw):
        pass

from .const import (
    CONF_AUTO_DOWNLOAD,
    DEFAULT_SCAN_INTERVAL,
    JUDETE,
)

_LOGGER = logging.getLogger(__name__)

JSON_URL = "https://www.meteoromania.ro/wp-json/meteoapi/v2/avertizari-generale"


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

    general_message_sensor = ANMGeneralMessageSensor(hass, alert_sensor)
    map_download_sensor = ANMMapDownloadSensor(hass, id_sensor, True)
    map_color_sensor = ANMMapColorSensor(hass, judet_cod, judet_nume, id_sensor)

    entities = [
        alert_sensor,
        id_sensor,
        message_sensor,
        general_message_sensor,
        map_download_sensor,
        map_color_sensor,
    ]
    async_add_entities(entities, update_before_add=True)
class ANMGeneralMessageSensor(Entity):
    """Senzor pentru mesajul meteo general (toate avertizările)."""

    def __init__(self, hass, alert_sensor):
        self._hass = hass
        self._alert_sensor = alert_sensor
        self._state = "liniste"
        self._attributes = {
            "tip_cod": "Verde",
            "mesaj_complet": "Nu sunt avertizări meteo generale active.",
            "friendly_name": "Mesaj Meteo General",
        }

    @property
    def name(self):
        return "Mesaj Meteo General"

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
        return "anm_mesaj_meteo_general"

    @property
    def available(self):
        return self._alert_sensor.state not in [None, "unknown", "unavailable"]

    async def async_update(self, now=None):
        await self._process_alerts()

    async def _process_alerts(self):
        avertizari = self._alert_sensor.extra_state_attributes.get("avertizari")
        if not avertizari:
            self._state = "liniste"
            self._attributes = {
                "tip_cod": "Verde",
                "mesaj_complet": "Nu sunt avertizări meteo generale active.",
                "friendly_name": "Mesaj Meteo General",
            }
            return

        self._state = "alerta"
        max_code = max([int(a.get("culoare", 0)) for a in avertizari])
        tip_cod_map = {3: "Rosu", 2: "Portocaliu", 1: "Galben", 0: "Informare"}
        tip_cod = tip_cod_map.get(max_code, "Verde")

        mesaje = []
        for item in avertizari:
            msg_raw = item.get("mesaj", "")
            msg_raw = msg_raw.replace("<br />", "\n").replace("</p>", "\n")
            msg_raw = re.sub(r"<[^>]*>", "", msg_raw)
            msg_raw = msg_raw.replace("&nbsp;", " ").replace("&ndash;", "-").strip()
            msg_final = re.sub(r"\n\s*\n", "\n\n", msg_raw).strip()
            mesaje.append(msg_final)

        mesaj_complet = "\n\n".join(mesaje).strip()
        self._attributes = {
            "tip_cod": tip_cod,
            "mesaj_complet": mesaj_complet if mesaj_complet else "Nu sunt avertizări meteo generale active.",
            "friendly_name": "Mesaj Meteo General",
        }



class ANMAlertSensor(Entity):
    """Senzor pentru lista de avertizări generale ANM cu cache persistent async."""

    _CACHE_FILE = ".anm_alert_cache.json"  # comun pentru toți senzorii

    def __init__(self, hass, id_sensor=None):
        self._hass = hass
        self._id_sensor = id_sensor
        self._state = None
        self._attributes = {}
        self._last_success_ts = None
        self._judet_name_to_code = {v.lower(): k for k, v in JUDETE.items()}
        self._active_source = None  # 'json' sau 'html'
        self._last_api_check = 0  # timestamp ultimei verificări API
        self._api_check_interval = 300  # verificăm API-ul la fiecare 5 minute când suntem pe HTML

    async def _save_to_cache(self, api_raw=None):
        cache_data = {
            "alert_state": self._state,
            "alert_attrs": self._attributes,
        }
        if api_raw is not None:
            cache_data["api_raw"] = api_raw
        cache_path = self._hass.config.path(self._CACHE_FILE)
        def _write_cache(path, data):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        try:
            await self._hass.async_add_executor_job(_write_cache, cache_path, cache_data)
            _LOGGER.debug("Cache ANMAlertSensor salvat la %s", cache_path)
        except Exception as exc:
            _LOGGER.warning("Eroare la salvarea cache ANMAlertSensor: %s", exc)

    async def _load_from_cache(self):
        cache_path = self._hass.config.path(self._CACHE_FILE)
        def _read_cache(path):
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        try:
            data = await self._hass.async_add_executor_job(_read_cache, cache_path)
            if data:
                self._state = data.get("alert_state")
                self._attributes = data.get("alert_attrs", {})
                # Fallback: dacă avertizari e gol și există api_raw, încearcă să extragi avertizări din api_raw
                avertizari = self._attributes.get("avertizari", [])
                if (not avertizari or (isinstance(avertizari, list) and len(avertizari) == 0)) and "api_raw" in data:
                    api_raw = data["api_raw"]
                    # Extrage avertizari din api_raw (poate fi dict sau listă)
                    if isinstance(api_raw, dict):
                        raw_alerts = api_raw.get("avertizari", [])
                        if not raw_alerts and "avertizari" in api_raw:
                            # uneori avertizari poate fi dict gol
                            raw_alerts = []
                        # fallback: dacă nu există avertizari, încearcă să caute direct lista
                        if not raw_alerts and isinstance(api_raw.get("avertizari"), dict):
                            raw_alerts = list(api_raw["avertizari"].values())
                    elif isinstance(api_raw, list):
                        raw_alerts = api_raw
                    else:
                        raw_alerts = []
                    normalized = self._normalize_alerts(raw_alerts)
                    self._attributes["avertizari"] = normalized
                    self._attributes["numar_avertizari"] = len(normalized)
                    _LOGGER.info("Avertizări extrase din api_raw fallback: %s", len(normalized))
                _LOGGER.info("Date ANMAlertSensor încărcate din cache %s", cache_path)
                return True
        except Exception as exc:
            _LOGGER.warning("Eroare la încărcarea cache ANMAlertSensor: %s", exc)
        return False

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
        """Actualizează avertizările doar cu fallback pe cache persistent (NU HTML, NU alte surse)."""
        prev_state = self._state
        prev_attrs = self._attributes.copy()
        current_time = int(asyncio.get_event_loop().time())

        try:
            async with async_timeout.timeout(10):
                session = async_get_clientsession(self._hass, verify_ssl=False)
                try:
                    self._last_api_check = current_time
                    async with session.get(JSON_URL) as response:
                        if response.status == 200:
                            data = await response.json()
                            avertizari_raw = data.get("avertizari", []) if isinstance(data, dict) else []
                            avertizari = self._normalize_alerts(avertizari_raw)
                            _LOGGER.warning("[DEBUG] avertizari_raw (API): %s", avertizari_raw)
                            _LOGGER.warning("[DEBUG] avertizari normalizate (API): %s", avertizari)
                            _LOGGER.warning("[DEBUG] numar_avertizari (API): %d", len(avertizari))

                            # MODIFICARE: dacă avertizari e gol, folosește fallback din cache persistent
                            if not avertizari:
                                _LOGGER.warning("Răspuns ANM JSON fără avertizări; încerc fallback la cache persistent")
                                loaded = await self._load_from_cache()
                                if loaded:
                                    _LOGGER.info("Fallback la cache persistent reușit (avertizări din cache)")
                                    # Log și avertizările din cache
                                    cache_avertizari = self._attributes.get("avertizari", [])
                                    _LOGGER.warning("[DEBUG] avertizari din cache: %s", cache_avertizari)
                                    _LOGGER.warning("[DEBUG] numar_avertizari (cache): %d", len(cache_avertizari))
                                    return
                                else:
                                    _LOGGER.warning("Fallback la cache persistent eșuat; păstrez ultima stare disponibilă")
                                    if prev_attrs:
                                        self._state = prev_state
                                        self._attributes = prev_attrs
                                    else:
                                        self._state = "unavailable"
                                    return

                            self._active_source = 'json'
                            self._state = "alerta" if len(avertizari) > 0 else "liniste"
                            self._last_success_ts = current_time
                            # Păstrează TOATE atributele din API/cache, nu doar pentru un județ
                            self._attributes = dict(data)
                            self._attributes.update({
                                "numar_avertizari": len(avertizari),
                                "avertizari": avertizari,
                                "friendly_name": "Avertizari Meteo ANM",
                                "sursa": "json",
                                "sursa_activa": self._active_source,
                            })
                            await self._save_to_cache(data)
                            return

                        _LOGGER.warning(
                            "Eroare HTTP %s la API JSON; fallback la cache persistent",
                            response.status,
                        )
                except Exception as exc_json:
                    _LOGGER.warning("Eroare la API JSON; fallback la cache persistent: %s", exc_json)

                # Fallback: doar cache persistent
                loaded = await self._load_from_cache()
                if loaded:
                    _LOGGER.warning("Sursa ANM (API JSON) a eșuat, am încărcat datele din cache persistent.")
                    # Log și avertizările din cache
                    cache_avertizari = self._attributes.get("avertizari", [])
                    _LOGGER.warning("[DEBUG] avertizari din cache: %s", cache_avertizari)
                    _LOGGER.warning("[DEBUG] numar_avertizari (cache): %d", len(cache_avertizari))
                    return
                # Dacă nu există cache persistent, fallback la in-memory
                if prev_attrs:
                    self._state = prev_state
                    self._attributes = prev_attrs
                else:
                    self._state = "unavailable"
                return
        except Exception as exc:
            _LOGGER.warning(
                "Eroare la actualizarea avertizărilor generale; păstrez ultima stare: %s",
                exc,
            )
            loaded = await self._load_from_cache()
            if loaded:
                # Log și avertizările din cache
                cache_avertizari = self._attributes.get("avertizari", [])
                _LOGGER.warning("[DEBUG] avertizari din cache: %s", cache_avertizari)
                _LOGGER.warning("[DEBUG] numar_avertizari (cache): %d", len(cache_avertizari))
                return
            if prev_attrs:
                self._state = prev_state
                self._attributes = prev_attrs
            else:
                self._state = "unavailable"


    # Metoda _parse_html_alerts și orice fallback HTML au fost eliminate complet.

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
        """
        Normalizează lista de avertizări: returnează exact lista oferită de API sau cache,
        fără replicare pe toate județele. Fiecare element trebuie să aibă cheile: judet, culoare, mesaj.
        """
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
            except Exception:
                color_val = 0

            # Acceptă direct structura: cu "judet" sau "judete" (listă)
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
    """Senzor pentru lista de ID-uri de avertizare active cu cache persistent async."""
    _CACHE_FILE = ".anm_alert_cache.json"  # comun cu ANMAlertSensor
    async def _save_to_cache(self):
        cache_path = self._hass.config.path(self._CACHE_FILE)
        def _update_cache(path, state, attrs):
            data = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data["id_state"] = state
            data["id_attrs"] = attrs
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        try:
            await self._hass.async_add_executor_job(_update_cache, cache_path, self._state, self._attributes)
            _LOGGER.debug("Cache ANMAlertIDSensor salvat la %s", cache_path)
        except Exception as exc:
            _LOGGER.warning("Eroare la salvarea cache ANMAlertIDSensor: %s", exc)

    async def _load_from_cache(self):
        cache_path = self._hass.config.path(self._CACHE_FILE)
        def _read_cache(path):
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        try:
            data = await self._hass.async_add_executor_job(_read_cache, cache_path)
            if data and "id_state" in data:
                self._state = data.get("id_state", "0")
                self._attributes = data.get("id_attrs", {})
                _LOGGER.info("Date ANMAlertIDSensor încărcate din cache %s", cache_path)
                return True
        except Exception as exc:
            _LOGGER.warning("Eroare la încărcarea cache ANMAlertIDSensor: %s", exc)
        return False

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
        """Actualizare ID-uri ANM dezactivată (fără fallback HTML)."""
        _LOGGER.warning("Actualizarea ID-urilor ANM din HTML a fost dezactivată. Senzorul nu va returna date noi.")
        loaded = await self._load_from_cache()
        if loaded:
            return
        self._state = "0"
        self._attributes = {
            "id_list": [],
            "numar_id": 0,
            "friendly_name": "ANM Avertizare ID (dezactivat)",
        }


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
        tip_cod_map = {3: "Rosu", 2: "Portocaliu", 1: "Galben", 0: "Informare"}
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
