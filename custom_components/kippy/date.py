"""Date platform for Kippy integration."""

from __future__ import annotations

import contextlib
import logging
from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .helpers import build_device_info
from .models import KippyConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KippyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kippy date entities."""
    coordinator = entry.runtime_data.coordinator

    entities = []
    for pet in coordinator.data.get("pets", []):
        pet_id = pet.get("petID")
        if pet_id:
            # "from" kommt alphabetisch vor "to"
            # -> Garantiert die richtige Anzeigereihenfolge
            entities.append(KippyHistoryDate(pet_id, pet, "from"))
            entities.append(KippyHistoryDate(pet_id, pet, "to"))

    async_add_entities(entities)


class KippyHistoryDate(DateEntity, RestoreEntity):
    """Date entity for selecting history export ranges."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar"

    def __init__(self, pet_id: str, pet_data: dict, date_type: str) -> None:
        """Initialize the date entity."""
        self._pet_id = pet_id
        self._pet_data = pet_data
        self._date_type = date_type

        # Der Name taucht in der UI auf. Kein pet_name hier einfügen!
        self._attr_name = f"History {date_type.capitalize()}"
        self._attr_unique_id = f"{pet_id}_history_{date_type}"
        self._attr_native_value = date.today()

    @property
    def device_info(self):
        """Link to the pet's device."""
        return build_device_info(self._pet_id, self._pet_data)

    async def async_added_to_hass(self) -> None:
        """Restore the last saved state when starting HA."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state not in (None, "unknown", "unavailable"):
            with contextlib.suppress(ValueError):
                self._attr_native_value = date.fromisoformat(state.state)

    async def async_set_value(self, value: date) -> None:
        """Update the value from the UI."""
        self._attr_native_value = value
        self.async_write_ha_state()

    def set_value(self, value: date) -> None:
        """Fallback to satisfy Pylint's abstract method check."""
        raise NotImplementedError("Synchronous set_value is not supported.")
