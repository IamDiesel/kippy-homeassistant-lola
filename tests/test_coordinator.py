"""Tests for the Kippy update coordinators and error edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.kippy.const import OPERATING_STATUS, OPERATING_STATUS_MAP
from custom_components.kippy.coordinator import (
    CoordinatorContext,
    KippyActivityCategoriesDataUpdateCoordinator,
    KippyDataUpdateCoordinator,
    KippyMapDataUpdateCoordinator,
)


# --- HELPER ---
def get_mock_context():
    """Create a standard context used by all Kippy coordinators."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    api = MagicMock()
    api.get_pet_kippy_list = AsyncMock()
    api.kippymap_action = AsyncMock()
    api.get_activity_categories = AsyncMock()

    return CoordinatorContext(hass=hass, config_entry=entry, api=api)


# --- TEST 1: Base Coordinator Success ---
@pytest.mark.asyncio
async def test_base_coordinator_success():
    """Test base coordinator successfully fetches the pet list."""
    ctx = get_mock_context()
    ctx.api.get_pet_kippy_list.return_value = [{"petID": 1, "kippyID": 123}]

    coord = KippyDataUpdateCoordinator(ctx.hass, ctx.config_entry, ctx.api)
    data = await coord._async_update_data()

    assert "pets" in data
    assert data["pets"][0]["kippyID"] == 123


# --- TEST 2: Base Coordinator Failure (Edge Case with ClientError) ---
@pytest.mark.asyncio
async def test_base_coordinator_api_error():
    """Test base coordinator catches ClientError exceptions and raises UpdateFailed."""
    ctx = get_mock_context()
    # Simulate an HTTP / Network error using ClientError from aiohttp
    ctx.api.get_pet_kippy_list.side_effect = ClientError("Connection failed")

    coord = KippyDataUpdateCoordinator(ctx.hass, ctx.config_entry, ctx.api)

    # Ensure the integration does not crash, but raises Home Assistant's UpdateFailed
    with pytest.raises(UpdateFailed) as exc:
        await coord._async_update_data()
    assert "Error communicating with API" in str(exc.value)


# --- TEST 3: Map Coordinator Logic (Live Tracking) ---
@pytest.mark.asyncio
async def test_map_coordinator_logic_live():
    """Test map coordinator logic for live tracking operating status."""
    ctx = get_mock_context()
    # Provide the string "live" as it comes from the API
    ctx.api.kippymap_action.return_value = {
        "operating_status": "live",
        "contact_time": 1000,
        "fix_time": 1000,
    }

    coord = KippyMapDataUpdateCoordinator(ctx, kippy_id=123)
    data = await coord._async_update_data()

    # Verify the coordinator correctly parsed "live" into the mapped constant
    assert data["operating_status"] == OPERATING_STATUS_MAP[OPERATING_STATUS.LIVE]


# --- TEST 4: Map Coordinator Logic (Energy Saving) ---
@pytest.mark.asyncio
async def test_map_coordinator_logic_energy_saving():
    """Test map coordinator logic for energy saving mode."""
    ctx = get_mock_context()
    # Provide the numeric code for energy saving
    ctx.api.kippymap_action.return_value = {
        "operating_status": OPERATING_STATUS.ENERGY_SAVING
    }

    coord = KippyMapDataUpdateCoordinator(ctx, kippy_id=123)
    data = await coord._async_update_data()

    assert (
        data["operating_status"] == OPERATING_STATUS_MAP[OPERATING_STATUS.ENERGY_SAVING]
    )


# --- TEST 5: Map Coordinator Edge Case (Missing Data) ---
@pytest.mark.asyncio
async def test_map_coordinator_missing_data():
    """Test map coordinator handles completely empty API
    responses without operating status."""
    ctx = get_mock_context()
    ctx.api.kippymap_action.return_value = {}

    coord = KippyMapDataUpdateCoordinator(ctx, kippy_id=123)
    data = await coord._async_update_data()

    # If the response is empty, operating_status should be None
    assert data.get("operating_status") is None


# --- TEST 6: Activity Coordinator Failure (Edge Case with ClientError) ---
@pytest.mark.asyncio
async def test_activity_coordinator_api_error():
    """Test activity coordinator catches network errors and raises UpdateFailed."""
    ctx = get_mock_context()
    # Simulate a network error using ClientError
    ctx.api.get_activity_categories.side_effect = ClientError("Timeout")

    with patch("custom_components.kippy.coordinator.dt_util.now"):
        coord = KippyActivityCategoriesDataUpdateCoordinator(ctx, pet_ids=[1])
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
