"""Senzori pentru Alertă ANM Județ România."""
import logging
import re
import json
import os
from datetime import timedelta
import async_timeout
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

JSON_URL = "https://www.meteoromania.ro/wp-json/meteoapi/v2/avertizari-generale"
CACHE_DIR = "/root/homeassistant/.storage/anm_cache"
CACHE_FILE = f"{CACHE_DIR}/anm_alerta_cache.json"

async def async_setup_entry(hass, config_entry, async_add_entities):
    # Intervalul de actualizare din configurație (în minute)
    update_interval = timedelta(minutes=config_entry.data.get("update_interval", 10))
    judet_cod = config_entry.data.get("judet_cod", "B")
    judet_nume = config_entry.data.get("judet_nume", "București")

    alert_sensor = ANMAlertSensor(hass)
    id_sensor = ANMAlertIDSensor(hass)
    message_sensor = ANMMessageSensor(hass, judet_cod, judet_nume, alert_sensor)
    map_sensor = ANMMapSensor(hass, judet_cod, judet_nume, id_sensor)
    color_sensor = ANMMapColorSensor(hass, judet_cod, judet_nume, alert_sensor)

    # Adăugarea senzorilor
    async_add_entities([alert_sensor, id_sensor, message_sensor, map_sensor, color_sensor])

    # Definirea funcției de actualizare care se va executa la intervalul definit
    async def update_sensors(now):
        _LOGGER.debug("Se execută actualizarea senzorilor la intervalul setat.")
        await alert_sensor.async_update()
        await id_sensor.async_update()
        await message_sensor.async_update()
        await map_sensor.async_update()
        await color_sensor.async_update()

    # Programarea actualizării la intervalele setate
    async_track_time_interval(hass, update_sensors, update_interval)

class ANMAlertSensor(Entity):
    def __init__(self, hass):
        self._hass = hass
        self._state = None
        self._attributes = {}
        self._raw_data = []  # Păstrăm datele complete intern, nu în atribute

    @property
    def name(self):
        return "Avertizări Meteo ANM"

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
        return "anm_avertizari_meteo"

    async def async_update(self, now=None):
        _LOGGER.debug("Actualizare date Avertizări Meteo ANM")
        try:
            async with async_timeout.timeout(10):
                session = async_get_clientsession(self._hass)
                async with session.get(JSON_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data or isinstance(data, str):
                            _LOGGER.warning(f"Nu există date disponibile: {data}")
                            # Încercăm să încărcăm din cache
                            if await self._load_from_cache():
                                return
                            self._state = "inactive"
                            self._raw_data = []
                            self._attributes = {
                                "numar_avertizari": 0,
                                "judete_afectate": 0,
                                "mesaj": "Nu exista avertizari",
                                "friendly_name": "Avertizări Meteo ANM"
                            }
                            return

                        toate_avertizarile = []

                        avertizare = data.get('avertizare', None)
                        if isinstance(avertizare, dict):
                            avertizare = [avertizare]

                        if isinstance(avertizare, list):
                            for avertizare_item in avertizare:
                                if isinstance(avertizare_item, dict):
                                    for judet in avertizare_item.get('judet', []):
                                        if isinstance(judet, dict):
                                            try:
                                                avertizare_judet = {
                                                    "judet": judet.get('@attributes', {}).get('cod', 'necunoscut'),
                                                    "culoare": judet.get('@attributes', {}).get('culoare', 'necunoscut'),
                                                    "fenomene_vizate": avertizare_item.get('@attributes', {}).get('fenomeneVizate', 'necunoscut'),
                                                    "data_expirarii": avertizare_item.get('@attributes', {}).get('dataExpirarii', 'necunoscut'),
                                                    "data_aparitiei": avertizare_item.get('@attributes', {}).get('dataAparitiei', 'necunoscut'),
                                                    "intervalul": avertizare_item.get('@attributes', {}).get('intervalul', 'necunoscut'),
                                                    "mesaj": avertizare_item.get('@attributes', {}).get('mesaj', 'necunoscut'),
                                                    "id_avertizare": avertizare_item.get('@attributes', {}).get('idAvertizare', 'necunoscut')
                                                }
                                                toate_avertizarile.append(avertizare_judet)
                                            except KeyError as e:
                                                _LOGGER.error(f"Eroare la procesarea datelor pentru județ: {e}")
                                        else:
                                            _LOGGER.error("Judete nu este un dicționar, s-a primit: %s", type(judet))
                                else:
                                    _LOGGER.error("Avertizare nu este un dicționar, s-a primit: %s", type(avertizare_item))
                        else:
                            _LOGGER.error("Avertizare nu este un dicționar sau o listă validă, s-a primit: %s", type(avertizare))
                        
                        # Păstrăm datele complete intern
                        self._raw_data = toate_avertizarile
                        
                        if toate_avertizarile:
                            self._state = "active"
                            # În atribute stocăm doar un rezumat pentru a nu depăși limita de 16KB
                            judete_afectate = {}
                            for av in toate_avertizarile:
                                jud = av.get('judet', 'necunoscut')
                                culoare = av.get('culoare', '0')
                                if jud not in judete_afectate or int(culoare) > int(judete_afectate[jud]):
                                    judete_afectate[jud] = culoare
                            
                            self._attributes = {
                                "numar_avertizari": len(toate_avertizarile),
                                "judete_afectate": len(judete_afectate),
                                "judete_coduri": judete_afectate,
                                "friendly_name": "Avertizări Meteo ANM"
                            }
                        else:
                            self._state = "inactive"
                            self._attributes = {
                                "numar_avertizari": 0,
                                "judete_afectate": 0,
                                "mesaj": "Nu exista avertizari",
                                "friendly_name": "Avertizări Meteo ANM"
                            }
                        # Salvăm în cache
                        await self._save_to_cache()
                        _LOGGER.info("Senzor ANM actualizat cu succes.")
                    else:
                        _LOGGER.error(f"Eroare HTTP {response.status} la preluarea datelor ANM")
                        # Încercăm să încărcăm din cache
                        await self._load_from_cache()
        except Exception as e:
            _LOGGER.error(f"Eroare la actualizarea datelor ANM: {e}")
            # Încercăm să încărcăm din cache
            await self._load_from_cache()

    async def _save_to_cache(self):
        """Salvează datele în cache."""
        try:
            # Creăm directorul de cache dacă nu există
            os.makedirs(CACHE_DIR, exist_ok=True)
            cache_data = {
                "state": self._state,
                "attributes": self._attributes,
                "raw_data": self._raw_data
            }
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
            _LOGGER.debug("Date salvate în cache")
        except Exception as e:
            _LOGGER.error(f"Eroare la salvarea în cache: {e}")

    async def _load_from_cache(self):
        """Încarcă datele din cache."""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    cache_data = json.load(f)
                self._state = cache_data.get("state", "inactive")
                self._attributes = cache_data.get("attributes", {})
                self._raw_data = cache_data.get("raw_data", [])
                _LOGGER.info("Date încărcate din cache")
                return True
        except Exception as e:
            _LOGGER.error(f"Eroare la încărcarea din cache: {e}")
        return False


class ANMAlertIDSensor(Entity):
    """Senzor pentru ID-urile alertelor ANM."""

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
        return "mdi:identifier"

    @property
    def unique_id(self):
        return "anm_avertizare_id"

    async def async_update(self, now=None):
        _LOGGER.debug("Actualizare ID-uri Avertizări ANM")
        try:
            async with async_timeout.timeout(10):
                session = async_get_clientsession(self._hass)
                async with session.get(JSON_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extragem ID-urile din JSON
                        ids = set()
                        avertizare = data.get('avertizare', None)
                        if isinstance(avertizare, dict):
                            avertizare = [avertizare]
                        
                        if isinstance(avertizare, list):
                            for avertizare_item in avertizare:
                                if isinstance(avertizare_item, dict):
                                    id_avert = avertizare_item.get('@attributes', {}).get('idAvertizare', None)
                                    if id_avert:
                                        ids.add(str(id_avert))
                        
                        if ids:
                            # Sortează ID-urile și le unește cu virgulă
                            ids_sorted = sorted(list(ids), key=int, reverse=True)
                            self._state = ','.join(ids_sorted)
                            self._attributes = {
                                "id_list": ids_sorted,
                                "numar_id": len(ids_sorted),
                                "friendly_name": "ANM Avertizare ID"
                            }
                            # Salvăm în cache
                            await self._save_to_cache()
                            _LOGGER.info(f"ID-uri ANM găsite: {self._state}")
                        else:
                            self._state = "0"
                            self._attributes = {
                                "id_list": [],
                                "numar_id": 0,
                                "friendly_name": "ANM Avertizare ID"
                            }
                            _LOGGER.info("Nu s-au găsit ID-uri ANM active")
                    else:
                        _LOGGER.error(f"Eroare HTTP {response.status} la preluarea datelor ANM")
                        # Încercăm să încărcăm din cache
                        await self._load_from_cache()
        except Exception as e:
            _LOGGER.error(f"Eroare la actualizarea ID-urilor ANM: {e}")
            # Încercăm să încărcăm din cache
            await self._load_from_cache()

    async def _save_to_cache(self):
        """Salvează ID-urile în cache."""
        try:
            # Creăm directorul de cache dacă nu există
            os.makedirs(CACHE_DIR, exist_ok=True)
            cache_file = CACHE_FILE.replace('.json', '_ids.json')
            cache_data = {
                "state": self._state,
                "attributes": self._attributes
            }
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
            _LOGGER.debug("ID-uri salvate în cache")
        except Exception as e:
            _LOGGER.error(f"Eroare la salvarea ID-urilor în cache: {e}")

    async def _load_from_cache(self):
        """Încarcă ID-urile din cache."""
        try:
            cache_file = CACHE_FILE.replace('.json', '_ids.json')
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                self._state = cache_data.get("state", "0")
                self._attributes = cache_data.get("attributes", {
                    "id_list": [],
                    "numar_id": 0,
                    "friendly_name": "ANM Avertizare ID"
                })
                _LOGGER.info("ID-uri încărcate din cache")
                return True
        except Exception as e:
            _LOGGER.error(f"Eroare la încărcarea ID-urilor din cache: {e}")
        return False


class ANMMessageSensor(Entity):
    """Senzor pentru mesajul complet de avertizare pentru județul selectat."""

    def __init__(self, hass, judet_cod, judet_nume, alert_sensor):
        self._hass = hass
        self._judet_cod = judet_cod
        self._judet_nume = judet_nume
        self._alert_sensor = alert_sensor
        self._state = "liniste"
        self._attributes = {}

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
        """Sensor is available only if alert sensor has valid data."""
        return self._alert_sensor.state not in [None, "unknown", "unavailable"]

    async def async_update(self, now=None):
        """Update se face automat când alert_sensor are date noi."""
        await self._process_alerts()

    async def _process_alerts(self):
        """Procesează alertele pentru județul selectat."""
        # Folosim _raw_data în loc de atribute pentru a prelua datele complete
        if not hasattr(self._alert_sensor, '_raw_data') or not self._alert_sensor._raw_data:
            self._state = "liniste"
            self._attributes = {
                "tip_cod": "Verde",
                "mesaj_complet": f"Nu sunt avertizări active pentru județul {self._judet_nume}.",
                "friendly_name": f"Mesaj Meteo {self._judet_nume}"
            }
            return

        avertizari = self._alert_sensor._raw_data
        
        # Filtrăm alertele pentru județul curent
        gl_list = [a for a in avertizari if a.get('judet') == self._judet_cod]
        
        if not gl_list:
            self._state = "liniste"
            self._attributes = {
                "tip_cod": "Verde",
                "mesaj_complet": f"Nu sunt avertizări active pentru județul {self._judet_nume}.",
                "friendly_name": f"Mesaj Meteo {self._judet_nume}"
            }
            return
        
        self._state = "alerta"
        
        # Calculăm cel mai grav cod
        max_code = max([int(a.get('culoare', 0)) for a in gl_list])
        tip_cod_map = {3: "Rosu", 2: "Portocaliu", 1: "Galben", 0: "Verde"}
        tip_cod = tip_cod_map.get(max_code, "Verde")
        
        # Construim mesajul complet
        mesaje = []
        for item in gl_list:
            msg_raw = item.get('mesaj', '')
            
            # Curățăm HTML-ul
            msg_raw = msg_raw.replace('<br />', '\n').replace('</p>', '\n')
            msg_raw = re.sub(r'<[^>]*>', '', msg_raw)
            msg_raw = msg_raw.replace('&nbsp;', ' ').replace('&ndash;', '-').strip()
            
            # Filtrăm mesajul pe baza culorii
            cod = int(item.get('culoare', 0))
            
            if cod == 1:  # Galben
                msg_raw = re.sub(r'COD PORTOCALIU[\s\S]*?(?=COD|$)', '', msg_raw, flags=re.IGNORECASE)
                msg_raw = re.sub(r'COD RO[SȘ]U[\s\S]*?(?=COD|$)', '', msg_raw, flags=re.IGNORECASE)
            elif cod == 2:  # Portocaliu
                msg_raw = re.sub(r'COD GALBEN[\s\S]*?(?=COD|$)', '', msg_raw, flags=re.IGNORECASE)
                msg_raw = re.sub(r'COD RO[SȘ]U[\s\S]*?(?=COD|$)', '', msg_raw, flags=re.IGNORECASE)
            elif cod == 3:  # Roșu
                msg_raw = re.sub(r'COD GALBEN[\s\S]*?(?=COD|$)', '', msg_raw, flags=re.IGNORECASE)
                msg_raw = re.sub(r'COD PORTOCALIU[\s\S]*?(?=COD|$)', '', msg_raw, flags=re.IGNORECASE)
            
            # Curățăm rânduri goale duble
            msg_final = re.sub(r'\n\s*\n', '\n\n', msg_raw).strip()
            mesaje.append(msg_final)
        
        mesaj_complet = '\n\n'.join(mesaje).strip()
        
        self._attributes = {
            "tip_cod": tip_cod,
            "mesaj_complet": mesaj_complet if mesaj_complet else f"Nu sunt avertizări active pentru județul {self._judet_nume}.",
            "friendly_name": f"Mesaj Meteo {self._judet_nume}"
        }
        
        _LOGGER.info(f"Mesaj meteo actualizat pentru {self._judet_nume}: {self._state} ({tip_cod})")


class ANMMapSensor(Entity):
    """Senzor pentru URL-ul hărții meteo active."""

    def __init__(self, hass, judet_cod, judet_nume, id_sensor):
        self._hass = hass
        self._judet_cod = judet_cod
        self._judet_nume = judet_nume
        self._id_sensor = id_sensor
        self._state = None
        self._attributes = {}
        
        import time
        self._timestamp = int(time.time())

    @property
    def name(self):
        return "Harta Meteo Activă"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def icon(self):
        return "mdi:map-legend"

    @property
    def unique_id(self):
        return f"anm_harta_meteo_{self._judet_cod.lower()}"

    async def async_update(self, now=None):
        """Actualizare URL hartă în funcție de ID-urile active."""
        sensor_ids = self._id_sensor.state
        
        # Actualizăm timestamp-ul pentru cache busting
        import time
        self._timestamp = int(time.time())
        
        if sensor_ids and sensor_ids not in ['unknown', 'unavailable', '0', '']:
            # Preluăm primul ID din listă
            first_id = sensor_ids.split(',')[0]
            self._state = f"https://images.weserv.nl/?url=www.meteoromania.ro/wp-content/plugins/meteo/harti/harta.svg.php?id_avertizare={first_id}"
            url_direct = f"https://www.meteoromania.ro/wp-content/plugins/meteo/harti/harta.svg.php?id_avertizare={first_id}"
        else:
            # Fallback la harta generală
            self._state = f"https://images.weserv.nl/?url=www.meteoromania.ro/images/avertizari/harta.png&v={self._timestamp}"
            url_direct = "https://www.meteoromania.ro/images/avertizari/harta.png"
        
        self._attributes = {
            "ids_detectate": sensor_ids if sensor_ids else "0",
            "url_direct_anm": url_direct,
            "judet_selectat": self._judet_nume,
            "judet_cod": self._judet_cod,
            "friendly_name": "Harta Meteo Activă"
        }
        
        _LOGGER.debug(f"Hartă meteo actualizată pentru {self._judet_nume}: {self._state}")


class ANMMapColorSensor(Entity):
    """Senzor pentru culoarea județului pe hartă."""

    def __init__(self, hass, judet_cod, judet_nume, alert_sensor):
        self._hass = hass
        self._judet_cod = judet_cod
        self._judet_nume = judet_nume
        self._alert_sensor = alert_sensor
        self._state = "verde"
        self._attributes = {}

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
        elif self._state == "portocaliu":
            return "mdi:alert"
        elif self._state == "galben":
            return "mdi:alert-circle"
        elif self._state == "informare":
            return "mdi:information"
        return "mdi:check-circle"

    @property
    def unique_id(self):
        return f"anm_culoare_harta_{self._judet_cod.lower()}"

    async def async_update(self, now=None):
        """Actualizează culoarea pe baza datelor din API JSON."""
        # Folosim direct datele din alert_sensor._raw_data
        if not hasattr(self._alert_sensor, '_raw_data') or not self._alert_sensor._raw_data:
            self._state = "verde"
            self._attributes = {
                "judet_cod": self._judet_cod,
                "friendly_name": f"Culoare Hartă {self._judet_nume}"
            }
            return
        
        # Filtrăm alertele pentru județul curent
        alerte_judet = [a for a in self._alert_sensor._raw_data if a.get('judet') == self._judet_cod]
        
        if not alerte_judet:
            self._state = "verde"
            self._attributes = {
                "judet_cod": self._judet_cod,
                "friendly_name": f"Culoare Hartă {self._judet_nume}"
            }
            return
        
        # Determinăm cea mai gravă culoare (valoare numerică: 0=verde, 1=galben, 2=portocaliu, 3=rosu)
        max_culoare = 0
        for alerta in alerte_judet:
            try:
                culoare_val = int(alerta.get('culoare', 0))
                if culoare_val > max_culoare:
                    max_culoare = culoare_val
            except (ValueError, TypeError):
                continue
        
        # Convertim valoarea numerică în text
        culoare_map = {0: "verde", 1: "galben", 2: "portocaliu", 3: "rosu"}
        self._state = culoare_map.get(max_culoare, "verde")
        
        self._attributes = {
            "numar_alerte": len(alerte_judet),
            "judet_cod": self._judet_cod,
            "cod_culoare": max_culoare,
            "friendly_name": f"Culoare Hartă {self._judet_nume}"
        }
        
        _LOGGER.info(f"Culoare hartă pentru {self._judet_nume}: {self._state} (cod: {max_culoare})")
            self._state = "necunoscut"
