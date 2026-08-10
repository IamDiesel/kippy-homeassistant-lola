"""Tests for Kippy button entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError

from custom_components.kippy.button import (
    KippyActivityCategoriesButton,
    KippyRefreshMapAttributesButton,
    KippyRefreshPetsButton,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_button_async_setup_entry_creates_entities() -> None:
    """Test if async_setup_entry creates refresh and activity buttons for each pet."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    coordinator.data = {"pets": [{"petID": 1}]}

    # Modern runtime_data object mock
    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: MagicMock()}
    mock_data.activity_coordinator = MagicMock()
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    # Verify that entities were added
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    # Expect refresh map, activity, and refresh pets buttons
    assert len(entities) >= 3


@pytest.mark.asyncio
async def test_refresh_map_attributes_button_press() -> None:
    """Test pressing the Refresh Map Attributes button calls
    the API and updates coordinator data."""
    coordinator = MagicMock()
    coordinator.api.kippymap_action = AsyncMock(return_value={"ok": True})
    coordinator.process_new_data = MagicMock()
    coordinator.kippy_id = 123

    pet = {"petID": 1, "petName": "Lola"}
    button = KippyRefreshMapAttributesButton(coordinator, pet)

    await button.async_press()

    coordinator.api.kippymap_action.assert_called_once_with(123)
    coordinator.process_new_data.assert_called_once_with({"ok": True})


@pytest.mark.asyncio
async def test_activity_button_press() -> None:
    """Test pressing the Activity Categories button refreshes pet activity data."""
    coordinator = MagicMock()
    coordinator.async_refresh_pet = AsyncMock()

    pet = {"petID": 1, "petName": "Lola"}
    button = KippyActivityCategoriesButton(coordinator, pet)

    await button.async_press()

    coordinator.async_refresh_pet.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_refresh_pets_button_press_loaded() -> None:
    """Test pressing the Refresh Pets button
    reloads the config entry when loaded."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry_123"
    entry.state = ConfigEntryState.LOADED

    hass.config_entries.async_reload = AsyncMock()
    hass.async_create_task = MagicMock(side_effect=lambda coro: coro)

    button = KippyRefreshPetsButton(hass, entry)
    await button.async_press()

    hass.config_entries.async_reload.assert_called_once_with("entry_123")


@pytest.mark.asyncio
async def test_refresh_pets_button_press_not_loaded() -> None:
    """Test pressing the Refresh Pets button raises
    HomeAssistantError if entry is not loaded."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry_123"
    entry.state = ConfigEntryState.NOT_LOADED

    button = KippyRefreshPetsButton(hass, entry)

    with pytest.raises(HomeAssistantError):
        await button.async_press()
