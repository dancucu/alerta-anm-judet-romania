"""Senzori pentru Alertă ANM Județ România."""
import logging
import re
from datetime import timedelta
import async_timeout
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

JSON_URL = "https://www.meteoromania.ro/wp-json/meteoapi/v2/avertizari-generale"
HTML_URL = "https://www.meteoromania.ro/avertizari/"

async def async_setup_entry(hass, config_entry, async_add_entities):
    # Intervalul de actualizare din configurație (în minute)
    update_interval = timedelta(minutes=config_entry.data.get("update_interval", 10))
    judet_cod = config_entry.data.get("judet_cod", "B")
    judet_nume = config_entry.data.get("judet_nume", "București")

    alert_sensor = ANMAlertSensor(hass)
    id_sensor = ANMAlertIDSensor(hass)
    message_sensor = ANMMessageSensor(hass, judet_cod, judet_nume, alert_sensor)

    # Adăugarea senzorilor
    async_add_entities([alert_sensor, id_sensor, message_sensor])

    # Definirea funcției de actualizare care se va executa la intervalul definit
    async def update_sensors(now):
        _LOGGER.debug("Se execută actualizarea senzorilor la intervalul setat.")
        await alert_sensor.async_update()
        await id_sensor.async_update()
        # Message sensor se actualizează automat când alert_sensor se schimbă

    # Programarea actualizării la intervalele setate
    async_track_time_interval(hass, update_sensors, update_interval)

class ANMAlertSensor(Entity):
    def __init__(self, hass):
        self._hass = hass
        self._state = None
        self._attributes = {}

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
                            self._state = "inactive"
                            self._attributes = {
                                "avertizari": "Nu exista avertizari",
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
                                                    "mesaj": avertizare_item.get('@attributes', {}).get('mesaj', 'necunoscut')
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
                        
                        if toate_avertizarile:
                            self._state = "active"
                            self._attributes = {
                                "avertizari": toate_avertizarile,
                                "friendly_name": "Avertizări Meteo ANM"
                            }
                        else:
                            self._state = "inactive"
                            self._attributes = {
                                "avertizari": "Nu exista avertizari",
                                "friendly_name": "Avertizări Meteo ANM"
                            }
                        _LOGGER.info("Senzor ANM actualizat cu succes.")
                    else:
                        _LOGGER.error(f"Eroare HTTP {response.status} la preluarea datelor ANM")
        except Exception as e:
            _LOGGER.error(f"Eroare la actualizarea datelor ANM: {e}")


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
                session = async_get_clientsession(self._hass, verify_ssl=False)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                async with session.get(HTML_URL, headers=headers) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        
                        # Extrage toate ID-urile de tipul id_avertizare=XXXX
                        pattern = r'id_avertizare=(\d+)'
                        ids = list(set(re.findall(pattern, html_content)))
                        
                        if ids:
                            # Sortează ID-urile și le unește cu virgulă
                            ids_sorted = sorted(ids, key=int, reverse=True)
                            self._state = ','.join(ids_sorted)
                            self._attributes = {
                                "id_list": ids_sorted,
                                "numar_id": len(ids_sorted),
                                "friendly_name": "ANM Avertizare ID"
                            }
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
                        _LOGGER.error(f"Eroare HTTP {response.status} la preluarea paginii ANM")
        except Exception as e:
            _LOGGER.error(f"Eroare la actualizarea ID-urilor ANM: {e}")


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
        if not self._alert_sensor._attributes.get('avertizari'):
            self._state = "liniste"
            self._attributes = {
                "tip_cod": "Verde",
                "mesaj_complet": f"Nu sunt avertizări active pentru județul {self._judet_nume}.",
                "friendly_name": f"Mesaj Meteo {self._judet_nume}"
            }
            return

        avertizari = self._alert_sensor._attributes.get('avertizari', [])
        
        # Filtrăm alertele pentru județul curent
        if isinstance(avertizari, str):
            self._state = "liniste"
            self._attributes = {
                "tip_cod": "Verde",
                "mesaj_complet": avertizari,
                "friendly_name": f"Mesaj Meteo {self._judet_nume}"
            }
            return
        
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
