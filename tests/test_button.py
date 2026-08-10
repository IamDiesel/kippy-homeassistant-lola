"""Tests for Kippy button entities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError

from custom_components.kippy.button import (
    KippyActivityCategoriesButton,
    KippyHistoryExportButton,
    KippyRefreshMapAttributesButton,
    KippyRefreshPetsButton,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_button_async_setup_entry_creates_entities() -> None:
    """Test if async_setup_entry creates refresh and activity buttons for each pet."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
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
    hass.async_add_executor_job = AsyncMock()
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
    hass.async_add_executor_job = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "entry_123"
    entry.state = ConfigEntryState.NOT_LOADED

    button = KippyRefreshPetsButton(hass, entry)

    with pytest.raises(HomeAssistantError):
        await button.async_press()


@pytest.mark.asyncio
async def test_history_export_button_no_entities() -> None:
    """Test pressing the History Export button when date entities are missing."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    api = MagicMock()
    pet = {"petID": 1, "petName": "Lola"}

    # Mock entity registry
    entity_reg = MagicMock()
    entity_reg.async_get_entity_id.return_value = None

    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=entity_reg
    ):
        button = KippyHistoryExportButton(hass, api, pet)
        await button.async_press()

    api.get_positions_history.assert_not_called()


@pytest.mark.asyncio
async def test_history_export_button_no_states() -> None:
    """Test pressing the History Export button when states are missing."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    api = MagicMock()
    pet = {"petID": 1, "petName": "Lola"}

    # Mock entity registry
    entity_reg = MagicMock()
    entity_reg.async_get_entity_id.return_value = "date.fake"
    hass.states.get.return_value = None

    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=entity_reg
    ):
        button = KippyHistoryExportButton(hass, api, pet)
        await button.async_press()

    api.get_positions_history.assert_not_called()


@pytest.mark.asyncio
async def test_history_export_button_success() -> None:
    """Test pressing the History Export button successfully."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    api = AsyncMock()
    pet = {"petID": 1, "petName": "Lola"}

    entity_reg = MagicMock()
    entity_reg.async_get_entity_id.return_value = "date.fake"

    state_mock = MagicMock()
    state_mock.state = "2026-08-10"
    hass.states.get.return_value = state_mock

    # Mock return positions
    api.get_positions_history.return_value = [
        {"positionType": "GPS", "lat": 1.0, "lng": 2.0, "radius": 50},
        {
            "positionType": "WIFI",
            "lat": 1.1,
            "lng": 2.1,
            "radius": 150,
        },  # Skipped because radius > 100
        {"positionType": "SKIP", "lat": 1.2, "lng": 2.2},  # Skipped
        {},  # Skipped missing lat/lng
    ]

    with (
        patch(
            "homeassistant.helpers.entity_registry.async_get", return_value=entity_reg
        ),
        patch("os.makedirs"),
        patch("builtins.open", new_callable=MagicMock),
    ):
        button = KippyHistoryExportButton(hass, api, pet)

        # Test property
        assert button.device_info["name"] == "Kippy Lola"

        await button.async_press()

    api.get_positions_history.assert_called_once_with(
        1, "2026-08-10T00:00:00.000Z", "2026-08-10T23:59:59.999Z"
    )
    pass

    # Ensure sync methods raise NotImplementedError
    with pytest.raises(NotImplementedError):
        button.press()


@pytest.mark.asyncio
async def test_history_export_button_no_coords() -> None:
    """Test pressing the History Export button with no valid coords."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    api = AsyncMock()
    pet = {"petID": 1, "petName": "Lola"}

    entity_reg = MagicMock()
    entity_reg.async_get_entity_id.return_value = "date.fake"
    state_mock = MagicMock()
    state_mock.state = "2026-08-10"
    hass.states.get.return_value = state_mock

    api.get_positions_history.return_value = []

    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=entity_reg
    ):
        button = KippyHistoryExportButton(hass, api, pet)
        await button.async_press()

    api.get_positions_history.assert_called_once()
    hass.async_add_executor_job.assert_not_called()


# Also add tests for sync press methods
def test_sync_press_methods():
    button1 = KippyRefreshMapAttributesButton(MagicMock(), {"petID": 1})
    with pytest.raises(NotImplementedError):
        button1.press()

    button2 = KippyActivityCategoriesButton(MagicMock(), {"petID": 1})
    with pytest.raises(NotImplementedError):
        button2.press()

    button3 = KippyRefreshPetsButton(MagicMock(), MagicMock())
    with pytest.raises(NotImplementedError):
        button3.press()
