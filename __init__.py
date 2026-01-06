"""Integrare pentru Alertele ANM pe Județ."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "alerta_anm_judet_romania"


async def async_setup_entry(hass, entry):
    """Configurare integrare din config entry."""
    _LOGGER.info("Setup Alertă ANM Județ")
    return True


async def async_unload_entry(hass, entry):
    """Dezinstalare integrare."""
    _LOGGER.info("Unload Alertă ANM Județ")
    return True
