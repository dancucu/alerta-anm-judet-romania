"""Senzori pentru Alertă ANM Județ România."""
import logging
from datetime import timedelta
import async_timeout
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

JSON_URL = "https://www.meteoromania.ro/wp-json/meteoapi/v2/avertizari-generale"

async def async_setup_entry(hass, config_entry, async_add_entities):
    # Intervalul de actualizare din configurație (în minute)
    update_interval = timedelta(minutes=config_entry.data.get("update_interval", 10))

    sensor = ANMAlertSensor(hass)

    # Adăugarea senzorului
    async_add_entities([sensor])

    # Definirea funcției de actualizare care se va executa la intervalul definit
    async def update_sensor(now):
        _LOGGER.debug("Se execută actualizarea senzorului la intervalul setat.")
        await sensor.async_update()

    # Programarea actualizării la intervalele setate
    async_track_time_interval(hass, update_sensor, update_interval)

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
