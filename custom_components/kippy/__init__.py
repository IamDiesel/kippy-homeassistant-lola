"""The Kippy integration."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Awaitable

import voluptuous as vol
from aiohttp import ClientResponseError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import config_validation as cv

from .api import KippyApi
from .const import DOMAIN, PLATFORMS
from .coordinator import (
    ActivityRefreshContext,
    ActivityRefreshTimer,
    CoordinatorContext,
    KippyActivityCategoriesDataUpdateCoordinator,
    KippyDataUpdateCoordinator,
    KippyMapDataUpdateCoordinator,
)
from .helpers import (
    API_EXCEPTIONS,
    get_device_update_interval,
    get_map_refresh_settings,
    is_pet_subscription_active,
    normalize_kippy_identifier,
)
from .models import KippyConfigEntry, KippyData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: KippyConfigEntry) -> bool:
    """Set up Kippy from a config entry."""
    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)
    if not email or not password:
        return False

    hass.data.setdefault(DOMAIN, {})
    session = aiohttp_client.async_get_clientsession(hass)
    api = await KippyApi.async_create(session)

    try:
        await api.login(email, password)

        async def _async_reload_entry() -> None:
            if entry.state is not ConfigEntryState.LOADED:
                return
            await hass.config_entries.async_reload(entry.entry_id)

        coordinator = KippyDataUpdateCoordinator(
            hass, entry, api, on_new_pets=_async_reload_entry
        )
        await coordinator.async_config_entry_first_refresh()

        context = CoordinatorContext(hass, entry, api)
        map_coordinators, pet_ids = await _async_build_map_coordinators(
            context, coordinator
        )
        activity_coordinator = KippyActivityCategoriesDataUpdateCoordinator(
            context, pet_ids
        )
        await activity_coordinator.async_config_entry_first_refresh()

        activity_timers = _build_activity_timers(
            hass, coordinator, map_coordinators, activity_coordinator
        )
    except API_EXCEPTIONS as err:
        if isinstance(err, ClientResponseError) and getattr(err, "status", None) in (
            401,
            403,
        ):
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err

    entry.runtime_data = KippyData(
        api=api,
        coordinator=coordinator,
        map_coordinators=map_coordinators,
        activity_coordinator=activity_coordinator,
        activity_timers=activity_timers,
    )

    async def _async_options_updated(
        hass: HomeAssistant, updated_entry: KippyConfigEntry
    ) -> None:
        data = updated_entry.runtime_data
        if not data:
            return
        base_coordinator = data.coordinator

        base_coordinator.set_update_interval_minutes(
            get_device_update_interval(updated_entry)
        )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # --- Start of the custom service ---
    async def handle_export_history(call: ServiceCall):
        """Export the GPS history as a GeoJSON file."""
        pet_id = call.data.get("pet_id")
        from_date = call.data.get("from_date")
        to_date = call.data.get("to_date")

        # Resolve the actual pet name from the coordinator data
        pet_name = "Pet"
        for pet in coordinator.data.get("pets", []):
            if str(pet.get("petID")) == str(pet_id):
                pet_name = pet.get("petName", "Pet")
                break

        _LOGGER.info(
            "Exporting Kippy route for pet %s (%s) from %s to %s",
            pet_name,
            pet_id,
            from_date,
            to_date,
        )

        # 1. Fetch data from the API
        positions = await api.get_positions_history(pet_id, from_date, to_date)

        # 2. Filter and convert waypoints
        coords = []
        for pos in reversed(
            positions
        ):  # Reverse the list in case AWS sorts from newest to oldest
            # Ignore standby pings ("SKIP") and null coordinates
            if pos.get("positionType") == "SKIP" or pos.get("isSkip"):
                continue

            lat = pos.get("lat")
            lng = pos.get("lng")
            if not lat or not lng:
                continue

            # Ignore outliers (filter anything over 100m inaccuracy)
            if pos.get("radius", 999) > 100:
                continue

            # IMPORTANT: GeoJSON expects the format [Longitude, Latitude]!
            coords.append([lng, lat])

        if not coords:
            _LOGGER.warning(
                "No valid Kippy waypoints found in this time range for %s.", pet_name
            )
            return

        # 3. Build GeoJSON structure
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "name": f"{pet_name} Route",
                        "stroke": "#FF0000",
                        "stroke-width": 4,
                    },
                }
            ],
        }

        # 4. Write to the /config/www/ directory
        www_dir = hass.config.path("www")
        os.makedirs(www_dir, exist_ok=True)

        # Save the file per pet to support multiple Kippy devices
        file_path = os.path.join(www_dir, f"kippy_history_{pet_id}.geojson")

        def write_file():
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(geojson_data, f)

        await hass.async_add_executor_job(write_file)
        _LOGGER.info("GeoJSON file successfully saved to %s", file_path)

    hass.services.async_register(
        DOMAIN,
        "export_history",
        handle_export_history,
        schema=vol.Schema(
            {
                vol.Required("pet_id"): cv.string,
                vol.Required("from_date"): cv.string,
                vol.Required("to_date"): cv.string,
            }
        ),
    )
    # --- End of the custom service ---

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KippyConfigEntry) -> bool:
    """Unload Kippy config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = entry.runtime_data
        if data is not None:
            for timer in data.activity_timers.values():
                timer.async_cancel()
            shutdown_tasks: list[Awaitable[Any]] = []

            def _collect_shutdown(target: Any) -> None:
                shutdown = getattr(target, "async_shutdown", None)
                if shutdown is not None:
                    shutdown_tasks.append(shutdown())

            coordinator = data.coordinator
            if coordinator is not None:
                _collect_shutdown(coordinator)

            for map_coordinator in data.map_coordinators.values():
                _collect_shutdown(map_coordinator)

            activity_coordinator = data.activity_coordinator
            if activity_coordinator is not None:
                _collect_shutdown(activity_coordinator)

            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks)
    return unload_ok


async def _async_build_map_coordinators(
    context: CoordinatorContext,
    coordinator: KippyDataUpdateCoordinator,
) -> tuple[dict[int | str, KippyMapDataUpdateCoordinator], list[int | str]]:
    """Create map coordinators for pets with active subscriptions."""

    map_coordinators: dict[int | str, KippyMapDataUpdateCoordinator] = {}
    active_pet_ids: list[int | str] = []
    for pet in coordinator.data.get("pets", []):
        if not is_pet_subscription_active(pet):
            continue
        pet_id = pet.get("petID")
        if pet_id is None:
            continue
        kippy_id = normalize_kippy_identifier(pet, include_pet_id=True)
        if kippy_id is None:
            continue
        settings = get_map_refresh_settings(context.config_entry, pet_id)
        map_coordinator = KippyMapDataUpdateCoordinator(
            context, kippy_id, settings=settings
        )
        await map_coordinator.async_config_entry_first_refresh()
        map_coordinators[pet_id] = map_coordinator
        active_pet_ids.append(pet_id)
    return map_coordinators, active_pet_ids


def _build_activity_timers(
    hass: HomeAssistant,
    coordinator: KippyDataUpdateCoordinator,
    map_coordinators: dict[int | str, KippyMapDataUpdateCoordinator],
    activity_coordinator: KippyActivityCategoriesDataUpdateCoordinator,
) -> dict[int | str, ActivityRefreshTimer]:
    """Create timers that refresh activities after contact."""

    timers: dict[int | str, ActivityRefreshTimer] = {}
    for pet_id, map_coordinator in map_coordinators.items():
        context = ActivityRefreshContext(
            hass=hass,
            base=coordinator,
            map=map_coordinator,
            activity=activity_coordinator,
        )
        timers[pet_id] = ActivityRefreshTimer(context, pet_id)
    return timers
