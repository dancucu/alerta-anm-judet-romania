"""Config flow pentru Alertă ANM Județ."""
from homeassistant import config_entries

from .const import DOMAIN


class AlertaANMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pentru integrarea Alertă ANM."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Pasul de configurare inițial."""
        if user_input is not None:
            return self.async_create_entry(
                title="Alertă ANM Județ",
                data={}
            )

        return self.async_show_form(step_id="user")
