"""Tests for Kippy device tracker entities."""

from unittest.mock import MagicMock

import pytest

from custom_components.kippy.device_tracker import KippyPetTracker, async_setup_entry


@pytest.mark.asyncio
async def test_device_tracker_async_setup_entry_creates_entities() -> None:
    """Test if async_setup_entry creates device tracker entities
    with correct attributes."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    coordinator.data = {"pets": [{"petID": 1}]}

    map_coordinator = MagicMock()
    map_coordinator.data = {
        "gps_latitude": 48.7758,
        "gps_longitude": 9.1829,
        "gps_accuracy": 15,
        "battery": 80,
    }

    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: map_coordinator}
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1

    tracker = entities[0]
    assert isinstance(tracker, KippyPetTracker)

    # Verify the mapped properties
    assert tracker.latitude == 48.7758
    assert tracker.longitude == 9.1829
    assert tracker.location_accuracy == 15
    assert tracker.battery_level == 80
    assert tracker.source_type.value == "gps"
