"""Tests for Kippy binary sensor entities."""

from unittest.mock import MagicMock

import pytest

from custom_components.kippy.binary_sensor import (
    KippyFirmwareUpgradeAvailableBinarySensor,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_binary_sensor_async_setup_entry_creates_entities() -> None:
    """Test if async_setup_entry creates binary sensor entities."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    # Mocking a pet that needs a firmware upgrade
    coordinator.data = {"pets": [{"petID": 1, "firmware_need_upgrade": True}]}

    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1

    sensor = entities[0]
    assert isinstance(sensor, KippyFirmwareUpgradeAvailableBinarySensor)
    assert sensor.is_on is True
