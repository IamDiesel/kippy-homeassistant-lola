"""Tests for Kippy date entities."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from custom_components.kippy.date import KippyHistoryDate, async_setup_entry


@pytest.mark.asyncio
async def test_date_async_setup_entry_creates_entities() -> None:
    """Test if async_setup_entry creates date entities for from and to."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    coordinator.data = {"pets": [{"petID": 1}]}

    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    # Should create two entities: 'from' and 'to'
    assert len(entities) == 2
    assert isinstance(entities[0], KippyHistoryDate)


@pytest.mark.asyncio
async def test_date_set_value() -> None:
    """Test setting the date updates the state."""
    entity = KippyHistoryDate("1", {"petID": 1}, "from")
    entity.async_write_ha_state = MagicMock()

    test_date = date(2026, 8, 10)
    await entity.async_set_value(test_date)

    assert entity.native_value == test_date
    entity.async_write_ha_state.assert_called_once()

    # Synchronous set_value should raise NotImplementedError
    with pytest.raises(NotImplementedError):
        entity.set_value(test_date)
