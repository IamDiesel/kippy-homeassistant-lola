"""Tests for Kippy switch entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.kippy.switch import (
    KippyEnergySavingSwitch,
    KippyGpsDefaultSwitch,
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
