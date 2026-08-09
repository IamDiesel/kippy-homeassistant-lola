"""API endpoint for updating tracker settings."""

from __future__ import annotations

import json
from typing import Any, Dict

from ._base import BaseKippyApi

SEND_SETTING_MUTATION = """
mutation sendSetting($setting: Setting!) {
  sendSetting(setting: $setting) {
    code
    message
  }
}
"""


class SettingsEndpoint(BaseKippyApi):
    """Mixin implementing device settings updates."""

    async def modify_kippy_settings(
        self,
        kippy_id: int | str,
        *,
        update_frequency: float | None = None,
        gps_on_default: bool | None = None,
        energy_saving_mode: bool | None = None,
    ) -> Dict[str, Any]:
        """Modify settings for a specific device via GraphQL."""

        responses = {}

        # 1. Update Frequency und GPS On Default
        # In GraphQL wird beides als stringifiziertes JSON im 'updateObject' übergeben.
        if update_frequency is not None or gps_on_default is not None:
            # Wenn Home Assistant übergibt das Intervall in Minuten
            # die API Minuten erwartet.
            freq_mins = (
                int(float(update_frequency)) if update_frequency is not None else 60
            )
            gps_on = bool(gps_on_default) if gps_on_default is not None else True

            update_obj = json.dumps(
                {"updateFrequency": freq_mins, "enableGpsOnDefault": gps_on}
            )

            variables = {
                "setting": {
                    "operationType": "UPDATE",
                    "settingType": "UPDATE_FREQUENCY",
                    "deviceId": str(kippy_id),
                    "updateObject": update_obj,
                }
            }

            responses["update_frequency"] = await self.execute_graphql(
                SEND_SETTING_MUTATION, variables
            )

        # 2. Energy Saving Mode
        if energy_saving_mode is not None:
            op_type = "ACTIVATE" if energy_saving_mode else "DEACTIVATE"

            variables = {
                "setting": {
                    "operationType": op_type,
                    "settingType": "ENERGY_SAVING_ZONE",
                    "deviceId": str(kippy_id),
                    "modeType": "SENTINEL",
                }
            }

            responses["energy_saving_mode"] = await self.execute_graphql(
                SEND_SETTING_MUTATION, variables
            )

        return responses
