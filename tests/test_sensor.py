"""Tests for Kippy sensor entities."""

from unittest.mock import MagicMock

import pytest

from custom_components.kippy.sensor import async_setup_entry


@pytest.mark.asyncio
async def test_sensor_async_setup_entry_creates_entities() -> None:
    """Test if async_setup_entry creates all sensor entities for an active pet."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    # is_pet_subscription_active requires expired_days < 0 to be true
    coordinator.data = {"pets": [{"petID": 1, "expired_days": -5}]}

    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: MagicMock()}
    mock_data.activity_coordinator = MagicMock()
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    # Kippy has many sensors (Battery, Steps, Energy Saving, etc.),
    # so we expect a large number of entities to be generated
    assert len(entities) > 10
