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


@pytest.mark.asyncio
async def test_device_update_frequency_number_invalid_value() -> None:
    """Test the device update frequency rejects out-of-range values."""
    entry = MagicMock()
    entry.options = {}

    coordinator = MagicMock()
    coordinator.config_entry = entry

    number = KippyDeviceUpdateFrequencyNumber(coordinator)
    number.hass = MagicMock()
    number.async_write_ha_state = MagicMock()

    with pytest.raises(ValueError):
        await number.async_set_native_value(0)


@pytest.mark.asyncio
async def test_device_update_frequency_number_no_change() -> None:
    """Test the device update frequency does nothing when value is unchanged."""
    from custom_components.kippy.helpers import DEVICE_UPDATE_INTERVAL_KEY

    entry = MagicMock()
    entry.options = {DEVICE_UPDATE_INTERVAL_KEY: 25}

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.set_update_interval_minutes = MagicMock()

    number = KippyDeviceUpdateFrequencyNumber(coordinator)
    number.hass = MagicMock()
    number.hass.config_entries.async_update_entry = MagicMock()
    number.async_write_ha_state = MagicMock()

    await number.async_set_native_value(25)

    number.hass.config_entries.async_update_entry.assert_not_called()
    coordinator.set_update_interval_minutes.assert_not_called()


def test_update_frequency_number_native_value() -> None:
    """Test the pet update frequency native value parsing."""
    coordinator = MagicMock()
    pet = {"petID": 1, "petName": "Lola"}
    number = KippyUpdateFrequencyNumber(coordinator, pet)

    pet["updateFrequency"] = None
    assert number.native_value is None

    pet["updateFrequency"] = 15
    assert number.native_value == 15

    pet["updateFrequency"] = "20"
    assert number.native_value == 20

    pet["updateFrequency"] = "bad"
    assert number.native_value is None


@pytest.mark.asyncio
async def test_update_frequency_number_without_kippy_id() -> None:
    """Test the pet update frequency stores locally when no kippy id exists."""
    pet = {"petID": 1, "petName": "Lola", "updateFrequency": 5}

    coordinator = MagicMock()
    coordinator.api.modify_kippy_settings = AsyncMock()

    number = KippyUpdateFrequencyNumber(coordinator, pet)
    number.async_write_ha_state = MagicMock()

    await number.async_set_native_value(12)

    coordinator.api.modify_kippy_settings.assert_not_called()
    assert pet["updateFrequency"] == 12


def test_idle_and_live_update_frequency_native_values() -> None:
    """Test idle and live update frequency native value conversion."""
    from custom_components.kippy.number import KippyLiveUpdateFrequencyNumber

    pet = {"petID": 1, "petName": "Lola"}

    map_coordinator = MagicMock()
    map_coordinator.idle_refresh = 600
    map_coordinator.live_refresh = 15

    idle = KippyIdleUpdateFrequencyNumber(map_coordinator, pet)
    assert idle.native_value == 10

    live = KippyLiveUpdateFrequencyNumber(map_coordinator, pet)
    assert live.native_value == 15


@pytest.mark.asyncio
async def test_live_update_frequency_number_set_value() -> None:
    """Test updating the live map update frequency."""
    from unittest.mock import patch

    from custom_components.kippy.number import KippyLiveUpdateFrequencyNumber

    pet = {"petID": 1, "petName": "Lola"}

    map_coordinator = MagicMock()
    map_coordinator.live_refresh = 15
    map_coordinator.async_set_live_refresh = AsyncMock()
    map_coordinator.config_entry = MagicMock()

    number = KippyLiveUpdateFrequencyNumber(map_coordinator, pet)
    number.hass = MagicMock()
    number.async_write_ha_state = MagicMock()

    with patch(
        "custom_components.kippy.number.async_update_map_refresh_settings",
        AsyncMock(),
    ) as update_helper:
        await number.async_set_native_value(8)

        map_coordinator.async_set_live_refresh.assert_called_once_with(8)
        update_helper.assert_called_once()


@pytest.mark.asyncio
async def test_activity_refresh_delay_number() -> None:
    """Test the activity refresh delay number entity."""
    from custom_components.kippy.number import KippyActivityRefreshDelayNumber

    pet = {"petID": 1, "petName": "Lola"}
    timer = MagicMock()
    timer.delay_minutes = 5
    timer.async_set_delay = AsyncMock()

    number = KippyActivityRefreshDelayNumber(timer, pet)
    number.async_write_ha_state = MagicMock()

    assert number.native_value == 5
    assert number.device_info["name"] == "Kippy Lola"

    await number.async_set_native_value(10)
    timer.async_set_delay.assert_called_once_with(10)


def test_number_sync_methods_raise_error() -> None:
    """Test all number entities raise NotImplementedError for sync updates."""
    from custom_components.kippy.number import (
        KippyActivityRefreshDelayNumber,
        KippyLiveUpdateFrequencyNumber,
    )

    pet = {"petID": 1, "petName": "Lola"}
    coordinator = MagicMock()
    map_coordinator = MagicMock()
    map_coordinator.idle_refresh = 300
    map_coordinator.live_refresh = 15

    device = KippyDeviceUpdateFrequencyNumber(coordinator)
    with pytest.raises(NotImplementedError):
        device.set_native_value(1)

    update = KippyUpdateFrequencyNumber(coordinator, pet)
    with pytest.raises(NotImplementedError):
        update.set_native_value(1)

    idle = KippyIdleUpdateFrequencyNumber(map_coordinator, pet)
    with pytest.raises(NotImplementedError):
        idle.set_native_value(1)

    live = KippyLiveUpdateFrequencyNumber(map_coordinator, pet)
    with pytest.raises(NotImplementedError):
        live.set_native_value(1)

    delay = KippyActivityRefreshDelayNumber(MagicMock(), pet)
    with pytest.raises(NotImplementedError):
        delay.set_native_value(1)
