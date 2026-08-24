"""Config flow pentru Alertă ANM Județ."""
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import DOMAIN, JUDETE, DEFAULT_SCAN_INTERVAL, CONF_AUTO_DOWNLOAD, CONF_AUTO_SWITCH_MAP


class AlertaANMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pentru integrarea Alertă ANM."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Pasul de configurare inițial."""
        errors = {}
        
        if user_input is not None:
            judet_cod = user_input["judet"]
            judet_nume = JUDETE.get(judet_cod, judet_cod)
            
            await self.async_set_unique_id(f"{DOMAIN}_{judet_cod.lower()}")
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"Alertă ANM - {judet_nume}",
                data={
                    "judet_cod": judet_cod,
                    "judet_nume": judet_nume,
                    "update_interval": user_input.get("update_interval", DEFAULT_SCAN_INTERVAL)
                }
            )

        # Sortăm județele după nume pentru afișare mai ușoară
        judete_sortate = {k: v for k, v in sorted(JUDETE.items(), key=lambda x: x[1])}
        
        data_schema = vol.Schema({
            vol.Required("judet"): vol.In(judete_sortate),
            vol.Optional("update_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=60)
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "judet": "Selectează județul pentru care vrei să primești avertizări meteo"
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Obține options flow."""
        return AlertaANMOptionsFlow()


class AlertaANMOptionsFlow(config_entries.OptionsFlow):
    """Options flow pentru Alertă ANM.

    Do not set self.config_entry manually here: since Home Assistant Core
    2024.12, OptionsFlow provides self.config_entry as a read-only property
    that HA sets automatically. Assigning it in __init__ (the old pattern)
    logs a deprecation warning from 2024.12 onward and raises
    AttributeError: property 'config_entry' has no setter starting with
    Home Assistant Core 2025.12, which breaks this integration's Options
    dialog entirely on current HA versions.
    """

    async def async_step_init(self, user_input=None):
        """Gestionare opțiuni."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "update_interval",
                    default=self.config_entry.options.get("update_interval", self.config_entry.data.get("update_interval", DEFAULT_SCAN_INTERVAL))
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Optional(
                    CONF_AUTO_DOWNLOAD,
                    default=self.config_entry.options.get(CONF_AUTO_DOWNLOAD, False)
                ): bool,
                vol.Optional(
                    CONF_AUTO_SWITCH_MAP,
                    default=self.config_entry.options.get(CONF_AUTO_SWITCH_MAP, True)
                ): bool,
            })
        )
