"""Tests for Kippy switch entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.kippy.switch import (
    KippyEnergySavingSwitch,
    KippyGpsDefaultSwitch,
    KippyIgnoreLBSSwitch,
    KippyLiveTrackingSwitch,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_switch_async_setup_entry_creates_entities() -> None:
    """Test if async_setup_entry successfully creates all switch entities for a pet."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    # Mocking pet data
    coordinator.data = {"pets": [{"petID": 1}]}

    # Modern runtime_data object mock
    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: MagicMock()}
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    # Verify that entities were passed to Home Assistant
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    # We expect EnergySaving, LiveTracking, IgnoreLBS, and GpsDefault switches
    assert len(entities) == 4


@pytest.mark.asyncio
async def test_energy_saving_switch_turn_on_off() -> None:
    """Test turning the energy saving switch on and off triggers the API."""
    pet = {"petID": "1", "petName": "Lola", "energySavingMode": 0, "kippyID": 123}

    coordinator = MagicMock()
    coordinator.data = {"pets": [pet]}
    coordinator.api.modify_kippy_settings = AsyncMock()

    map_coord = MagicMock()

    switch = KippyEnergySavingSwitch(coordinator, pet, map_coord)
    switch.async_write_ha_state = MagicMock()

    # Turn ON
    await switch.async_turn_on()
    coordinator.api.modify_kippy_settings.assert_called_with(
        123, energy_saving_mode=True
    )
    assert switch.is_on

    # Turn OFF
    await switch.async_turn_off()
    coordinator.api.modify_kippy_settings.assert_called_with(
        123, energy_saving_mode=False
    )
    assert not switch.is_on


@pytest.mark.asyncio
async def test_live_tracking_switch_turn_on_off() -> None:
    """Test toggling live tracking calls the map API."""
    pet = {"petID": 1, "petName": "Lola"}

    coordinator = MagicMock()
    coordinator.kippy_id = 123
    coordinator.data = {"operating_status": "idle"}
    coordinator.api.kippymap_action = AsyncMock(
        return_value={"operating_status": "live"}
    )
    coordinator.process_new_data = MagicMock()

    switch = KippyLiveTrackingSwitch(coordinator, pet)
    switch.async_write_ha_state = MagicMock()

    # Turn ON
    await switch.async_turn_on()
    coordinator.api.kippymap_action.assert_called()
    assert coordinator.process_new_data.call_count == 1

    # Turn OFF
    await switch.async_turn_off()
    assert coordinator.api.kippymap_action.call_count == 2
    assert coordinator.process_new_data.call_count == 2


@pytest.mark.asyncio
async def test_gps_default_switch_turn_on_off() -> None:
    """Test turning the GPS default activation switch on and off."""
    pet = {"petID": "1", "gpsOnDefault": 0, "kippyID": 123}

    coordinator = MagicMock()
    coordinator.data = {"pets": [pet]}
    coordinator.api.modify_kippy_settings = AsyncMock()

    switch = KippyGpsDefaultSwitch(coordinator, pet)
    switch.async_write_ha_state = MagicMock()

    # Turn ON
    await switch.async_turn_on()
    coordinator.api.modify_kippy_settings.assert_called_with(123, gps_on_default=True)
    assert switch.is_on


@pytest.mark.asyncio
async def test_switch_sync_methods_raise_error() -> None:
    """Test sync methods raise NotImplementedError."""
    coordinator = MagicMock()
    map_coord = MagicMock()
    pet = {"petID": 1, "petName": "Lola", "kippyID": 1}

    switch1 = KippyEnergySavingSwitch(coordinator, pet, map_coord)
    with pytest.raises(NotImplementedError):
        switch1.turn_on()
    with pytest.raises(NotImplementedError):
        switch1.turn_off()

    switch2 = KippyLiveTrackingSwitch(map_coord, pet)
    with pytest.raises(NotImplementedError):
        switch2.turn_on()
    with pytest.raises(NotImplementedError):
        switch2.turn_off()

    switch3 = KippyGpsDefaultSwitch(coordinator, pet)
    with pytest.raises(NotImplementedError):
        switch3.turn_on()
    with pytest.raises(NotImplementedError):
        switch3.turn_off()

    switch4 = KippyIgnoreLBSSwitch(map_coord, pet)
    with pytest.raises(NotImplementedError):
        switch4.turn_on()
    with pytest.raises(NotImplementedError):
        switch4.turn_off()


@pytest.mark.asyncio
async def test_energy_saving_switch_handle_map_update() -> None:
    """Test map update logic for EnergySavingSwitch."""
    pet = {"petID": "1", "petName": "Lola", "energySavingMode": 0, "kippyID": 123}

    coordinator = MagicMock()
    coordinator.data = {"pets": [pet]}
    map_coord = MagicMock()

    switch = KippyEnergySavingSwitch(coordinator, pet, map_coord)
    switch.async_write_ha_state = MagicMock()

    # Empty map data
    map_coord.data = {}
    switch._handle_map_update()
    assert pet["energySavingMode"] == 0

    # Status matches ENERGY SAVING -> should update pet data if not pending
    map_coord.data = {"operating_status": "energy_saving"}
    pet["energySavingModePending"] = False
    switch._handle_map_update()
    assert pet["energySavingMode"] == 1

    # Status doesn't match, but pending is true
    map_coord.data = {"operating_status": "idle"}
    pet["energySavingModePending"] = True
    pet["energySavingMode"] = 0
    switch._handle_map_update()
    assert pet["energySavingModePending"] is False
    assert pet["energySavingMode"] == 0


@pytest.mark.asyncio
async def test_gps_default_switch_turn_off() -> None:
    """Test turn_off for GPS default switch."""
    pet = {"petID": "1", "gpsOnDefault": 1, "kippyID": 123}

    coordinator = MagicMock()
    coordinator.data = {"pets": [pet]}
    coordinator.api.modify_kippy_settings = AsyncMock()

    switch = KippyGpsDefaultSwitch(coordinator, pet)
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_off()
    coordinator.api.modify_kippy_settings.assert_called_with(123, gps_on_default=False)
    assert switch.is_on is False


@pytest.mark.asyncio
async def test_live_tracking_switch_unavailable_turn_on_off() -> None:
    """Test live tracking switch when unavailable (energy saving mode)."""
    from homeassistant.exceptions import HomeAssistantError

    pet = {"petID": 1, "petName": "Lola"}

    coordinator = MagicMock()
    coordinator.kippy_id = 123
    coordinator.data = {"operating_status": "energy_saving"}

    switch = KippyLiveTrackingSwitch(coordinator, pet)
    switch.async_write_ha_state = MagicMock()

    with pytest.raises(
        HomeAssistantError,
        match="Live tracking cannot be enabled in energy saving mode",
    ):
        await switch.async_turn_on()

    with pytest.raises(
        HomeAssistantError,
        match="Live tracking cannot be disabled in energy saving mode",
    ):
        await switch.async_turn_off()


@pytest.mark.asyncio
async def test_ignore_lbs_switch_turn_on_off() -> None:
    """Test turning Ignore LBS switch on and off updates the coordinator."""
    pet = {"petID": 1, "petName": "Lola"}

    coordinator = MagicMock()
    coordinator.kippy_id = 123
    coordinator.ignore_lbs = False

    switch = KippyIgnoreLBSSwitch(coordinator, pet)
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()
    assert coordinator.ignore_lbs is True
    assert switch.is_on is True

    await switch.async_turn_off()
    assert coordinator.ignore_lbs is False
    assert switch.is_on is False
