"""Tests for Kippy number entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.kippy.number import (
    KippyDeviceUpdateFrequencyNumber,
    KippyIdleUpdateFrequencyNumber,
    KippyUpdateFrequencyNumber,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_number_async_setup_entry_creates_entities() -> None:
    """Test if async_setup_entry successfully creates all number entities."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    coordinator.data = {"pets": [{"petID": 1}]}

    # Modern runtime_data object mock
    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: MagicMock()}
    mock_data.activity_timers = {1: MagicMock()}
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    # Verify that entities were passed to Home Assistant
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    # We expect global device update freq, pet update freq,
    # idle, live, and activity delay numbers
    assert len(entities) == 5


@pytest.mark.asyncio
async def test_device_update_frequency_number_set_value() -> None:
    """Test updating the global device update frequency updates the config entry."""
    entry = MagicMock()
    entry.options = {}

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.set_update_interval_minutes = MagicMock()

    number = KippyDeviceUpdateFrequencyNumber(coordinator)

    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    number.hass = hass
    number.async_write_ha_state = MagicMock()

    # Change value to 25 minutes
    await number.async_set_native_value(25)

    # Verify config entry update is triggered
    hass.config_entries.async_update_entry.assert_called_once()
    coordinator.set_update_interval_minutes.assert_called_once_with(25)


@pytest.mark.asyncio
async def test_update_frequency_number_set_value() -> None:
    """Test updating a specific pet's update frequency triggers the API."""
    pet = {
        "petID": 1,
        "petName": "Lola",
        "updateFrequency": 5,
        "kippyID": 123,
        "gpsOnDefault": 1,
    }

    coordinator = MagicMock()
    coordinator.data = {"pets": [pet]}
    coordinator.api.modify_kippy_settings = AsyncMock(
        return_value={"update_frequency": 10}
    )

    number = KippyUpdateFrequencyNumber(coordinator, pet)
    number.async_write_ha_state = MagicMock()

    # Change value to 10
    await number.async_set_native_value(10)

    # Verify the API is called with the correct parameters
    coordinator.api.modify_kippy_settings.assert_called_once_with(
        123, update_frequency=10, gps_on_default=True
    )
    assert pet["updateFrequency"] == 10


@pytest.mark.asyncio
async def test_idle_update_frequency_number_set_value() -> None:
    """Test updating the idle map update frequency."""
    pet = {"petID": 1, "petName": "Lola"}

    map_coordinator = MagicMock()
    map_coordinator.idle_refresh = 300
    map_coordinator.async_set_idle_refresh = AsyncMock()
    map_coordinator.config_entry = MagicMock()

    number = KippyIdleUpdateFrequencyNumber(map_coordinator, pet)
    number.hass = MagicMock()
    number.async_write_ha_state = MagicMock()

    # We need to mock the external async_update_map_refresh_settings helper
    from unittest.mock import patch

    with patch(
        "custom_components.kippy.number.async_update_map_refresh_settings", AsyncMock()
    ) as update_helper:
        # 6 minutes
        await number.async_set_native_value(6)

        # Idle refresh works in seconds, so 6 min * 60 = 360 seconds
        map_coordinator.async_set_idle_refresh.assert_called_once_with(360)
        update_helper.assert_called_once()
