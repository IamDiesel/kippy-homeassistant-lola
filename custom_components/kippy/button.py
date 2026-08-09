"""Button entities for Kippy pets."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .coordinator import (
    KippyActivityCategoriesDataUpdateCoordinator,
    KippyDataUpdateCoordinator,
    KippyMapDataUpdateCoordinator,
)
from .entity import KippyMapEntity
from .helpers import build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Kippy button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: KippyDataUpdateCoordinator = data["coordinator"]
    map_coordinators: dict[int, KippyMapDataUpdateCoordinator] = data[
        "map_coordinators"
    ]
    activity_coordinator: KippyActivityCategoriesDataUpdateCoordinator = data[
        "activity_coordinator"
    ]
    api = data["api"]

    entities: list[ButtonEntity] = [KippyRefreshPetsButton(hass, entry)]

    for pet in coordinator.data.get("pets", []):
        map_coord = map_coordinators.get(pet["petID"])
        if not map_coord:
            continue

        entities.append(KippyRefreshMapAttributesButton(map_coord, pet))
        entities.append(KippyActivityCategoriesButton(activity_coordinator, pet))
        entities.append(KippyHistoryExportButton(hass, api, pet))

    async_add_entities(entities)


class KippyRefreshMapAttributesButton(KippyMapEntity, ButtonEntity):
    """Button to refresh Kippy map attributes immediately."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: KippyMapDataUpdateCoordinator, pet: dict[str, Any]
    ) -> None:
        super().__init__(coordinator, pet)
        self._attr_name = "Refresh Map Attributes"
        self._attr_unique_id = f"{self._pet_id}_refresh_map_attributes"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_translation_key = "refresh_map_attributes"

    async def async_press(self) -> None:
        data = await self.coordinator.api.kippymap_action(self.coordinator.kippy_id)
        self.coordinator.process_new_data(data)

    def press(self) -> None:
        raise NotImplementedError(
            "Synchronous button presses are not supported; use async_press instead."
        )


class KippyActivityCategoriesButton(ButtonEntity):
    """Button to manually refresh activity categories."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KippyActivityCategoriesDataUpdateCoordinator,
        pet: dict[str, Any],
    ) -> None:
        self.coordinator = coordinator
        self._pet_id = pet["petID"]
        self._pet_data = pet
        self._attr_name = "Refresh Activities"
        self._attr_unique_id = f"{self._pet_id}_refresh_activities"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_translation_key = "refresh_activities"

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_pet(self._pet_id)

    def press(self) -> None:
        raise NotImplementedError(
            "Synchronous button presses are not supported; use async_press instead."
        )

    @property
    def device_info(self) -> DeviceInfo:
        return build_device_info(self._pet_id, self._pet_data)


class KippyRefreshPetsButton(ButtonEntity):
    """Button to refresh the list of pets."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_name = "Refresh Pets"
        self._attr_unique_id = f"{entry.entry_id}_refresh_pets"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_translation_key = "refresh_pets"
        self._reloading = False

    async def async_press(self) -> None:
        if self._reloading or self.entry.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError("Entry is not loaded")
        self._reloading = True
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.entry.entry_id)
        )

    def press(self) -> None:
        raise NotImplementedError(
            "Synchronous button presses are not supported; use async_press instead."
        )


class KippyHistoryExportButton(ButtonEntity):
    """Button to trigger the GeoJSON history export for a pet."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, api, pet: dict[str, Any]) -> None:
        """Initialize the button."""
        self.hass = hass
        self.api = api
        self._pet_id = pet["petID"]
        self._pet_data = pet
        self._pet_name = pet.get("petName", "Pet")

        self._attr_name = "Download History Route"
        self._attr_unique_id = f"{self._pet_id}_export_history_button"
        self._attr_icon = "mdi:map-marker-path"

    @property
    def device_info(self) -> DeviceInfo:
        """Link to the pet's device."""
        return build_device_info(self._pet_id, self._pet_data)

    async def async_press(self) -> None:
        """Handle the button press."""
        entity_reg = er.async_get(self.hass)

        # Die Registrierung greift nun auf die 'date' Plattform zu
        start_entity_id = entity_reg.async_get_entity_id(
            "date", DOMAIN, f"{self._pet_id}_history_from"
        )
        end_entity_id = entity_reg.async_get_entity_id(
            "date", DOMAIN, f"{self._pet_id}_history_to"
        )

        if not start_entity_id or not end_entity_id:
            _LOGGER.error(
                "Start- oder Enddatum-Entität für %s nicht gefunden", self._pet_name
            )
            return

        start_state = self.hass.states.get(start_entity_id)
        end_state = self.hass.states.get(end_entity_id)

        if not start_state or not end_state:
            _LOGGER.error(
                "Konnte den Status der Datumsfelder für %s nicht lesen", self._pet_name
            )
            return

        # Die reinen Daten (YYYY-MM-DD) werden hier
        # mit der Uhrzeit für die API kombiniert
        from_date = f"{start_state.state}T00:00:00.000Z"
        to_date = f"{end_state.state}T23:59:59.999Z"

        _LOGGER.info(
            "Exportiere Route für %s von %s bis %s", self._pet_name, from_date, to_date
        )

        positions = await self.api.get_positions_history(
            self._pet_id, from_date, to_date
        )

        coords = []
        for pos in reversed(positions):
            if pos.get("positionType") == "SKIP" or pos.get("isSkip"):
                continue

            lat = pos.get("lat")
            lng = pos.get("lng")
            if not lat or not lng:
                continue

            if pos.get("radius", 999) > 100:
                continue

            coords.append([lng, lat])

        if not coords:
            _LOGGER.warning(
                "Keine gültigen Wegpunkte für %s im gewählten Zeitraum gefunden.",
                self._pet_name,
            )
            return

        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "name": f"{self._pet_name} Route",
                        "stroke": "#FF0000",
                        "stroke-width": 4,
                    },
                }
            ],
        }

        www_dir = self.hass.config.path("www")
        os.makedirs(www_dir, exist_ok=True)
        file_path = os.path.join(www_dir, f"kippy_history_{self._pet_id}.geojson")

        def write_file():
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(geojson_data, f)

        await self.hass.async_add_executor_job(write_file)
        _LOGGER.info(
            "Erfolgreich %s Wegpunkte in %s gespeichert.", len(coords), file_path
        )

    def press(self) -> None:
        raise NotImplementedError(
            "Synchronous button presses are not supported; use async_press instead."
        )
