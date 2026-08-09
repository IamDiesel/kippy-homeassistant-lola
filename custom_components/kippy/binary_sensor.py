"""Binary sensors for Kippy pets."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant

from .coordinator import KippyDataUpdateCoordinator
from .entity import KippyPetEntity
from .models import KippyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: KippyConfigEntry, async_add_entities
) -> None:
    """Set up Kippy binary sensors."""
    coordinator = entry.runtime_data.coordinator
    entities: list[BinarySensorEntity] = []
    for pet in coordinator.data.get("pets", []):
        entities.append(KippyFirmwareUpgradeAvailableBinarySensor(coordinator, pet))
    async_add_entities(entities)


class KippyFirmwareUpgradeAvailableBinarySensor(KippyPetEntity, BinarySensorEntity):
    """Binary sensor indicating firmware upgrade availability."""

    def __init__(
        self, coordinator: KippyDataUpdateCoordinator, pet: dict[str, Any]
    ) -> None:
        super().__init__(coordinator, pet)
        self._attr_name = "Firmware Upgrade available"
        self._attr_unique_id = f"{self._pet_id}_firmware_upgrade"
        self._attr_translation_key = "firmware_upgrade_available"

    @property
    def is_on(self) -> bool:
        return bool(self._pet_data.get("firmware_need_upgrade"))
