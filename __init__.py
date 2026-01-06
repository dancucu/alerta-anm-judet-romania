"""Integrare pentru Alertele ANM pe Județ."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "alerta_anm_judet_romania"


async def async_setup_entry(hass, entry):
    """Configurare integrare din config entry."""
    _LOGGER.info("Setup Alertă ANM Județ")
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    return True


async def async_unload_entry(hass, entry):
    """Dezinstalare integrare."""
    _LOGGER.info("Unload Alertă ANM Județ")
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
