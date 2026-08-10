"""Tests for the Kippy update coordinators and error edge cases."""

from datetime import timedelta
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


# --- TEST 7: Base coordinator interval and new pets handling ---
@pytest.mark.asyncio
async def test_coordinator_set_update_interval():
    """Test set_update_interval_minutes schedules a refresh only on change."""
    ctx = get_mock_context()
    coord = KippyDataUpdateCoordinator(ctx.hass, ctx.config_entry, ctx.api)

    with patch.object(coord, "_schedule_refresh") as mock_schedule:
        coord.set_update_interval_minutes(10)
        mock_schedule.assert_called_once()

        mock_schedule.reset_mock()
        coord.set_update_interval_minutes(10)
        mock_schedule.assert_not_called()


@pytest.mark.asyncio
async def test_coordinator_handle_new_pets():
    """Test _handle_new_pets triggers a reload when new pets appear."""
    ctx = get_mock_context()
    on_new_pets_mock = AsyncMock()
    coord = KippyDataUpdateCoordinator(
        ctx.hass, ctx.config_entry, ctx.api, on_new_pets=on_new_pets_mock
    )

    # Non-list input is coerced to an empty set
    coord._handle_new_pets(None)
    assert coord._known_pet_ids == set()

    # Initial load only records the known ids
    coord._handle_new_pets([{"petID": 1}])
    assert coord._known_pet_ids == {"1"}
    on_new_pets_mock.assert_not_called()

    # Same pet -> no reload
    coord._handle_new_pets([{"petID": 1}])
    on_new_pets_mock.assert_not_called()

    # New pet -> schedule reload
    coord._handle_new_pets([{"petID": 1}, {"petID": 2}])
    assert coord._pending_reload is True
    ctx.hass.async_create_task.assert_called_once()
    task_mock = coord._reload_task
    assert task_mock is not None

    # Run the reload wrapper and clear callback
    wrapper = ctx.hass.async_create_task.call_args[0][0]
    await wrapper
    on_new_pets_mock.assert_awaited_once()
    assert coord._pending_reload is False

    cb = task_mock.add_done_callback.call_args[0][0]
    cb(task_mock)
    assert coord._reload_task is None

    # When a reload is already pending, only ids are refreshed
    coord._pending_reload = True
    coord._handle_new_pets([{"petID": 1}, {"petID": 2}, {"petID": 3}])
    assert coord._known_pet_ids == {"1", "2", "3"}


# --- TEST 8: Base coordinator shutdown cancels reload task ---
@pytest.mark.asyncio
async def test_coordinator_async_shutdown():
    """Test async_shutdown cancels the pending reload task."""
    import asyncio

    ctx = get_mock_context()
    coord = KippyDataUpdateCoordinator(ctx.hass, ctx.config_entry, ctx.api)

    async def dummy_task():
        await asyncio.sleep(1)

    task = asyncio.create_task(dummy_task())
    coord._reload_task = task
    coord._pending_reload = False

    await coord.async_shutdown()
    assert task.cancelled()


# --- TEST 9: Map coordinator logic (starting live) ---
@pytest.mark.asyncio
async def test_map_coordinator_logic_starting_live():
    """Test map coordinator transitions to starting-live status."""
    from custom_components.kippy.const import OPERATING_STATUS_STARTING_LIVE

    ctx = get_mock_context()
    coord = KippyMapDataUpdateCoordinator(ctx, kippy_id=123)
    coord.data = {
        "operating_status": OPERATING_STATUS_MAP[OPERATING_STATUS.IDLE],
        "operating_status_code": OPERATING_STATUS.IDLE,
    }

    ctx.api.kippymap_action.return_value = {
        "operating_status": OPERATING_STATUS.LIVE,
        "contact_time": 1000,
        "fix_time": 2000,
    }

    data = await coord._async_update_data()
    assert data["operating_status"] == OPERATING_STATUS_STARTING_LIVE

    # Explicit 'starting_live' string is preserved
    ctx.api.kippymap_action.return_value = {
        "operating_status": OPERATING_STATUS_STARTING_LIVE,
    }
    data = await coord._async_update_data()
    assert data["operating_status"] == OPERATING_STATUS_STARTING_LIVE


# --- TEST 10: Activity coordinator refresh and getters ---
@pytest.mark.asyncio
async def test_activity_coordinator_refresh_pet_and_getters():
    """Test activity coordinator manual refresh and cached getters."""
    ctx = get_mock_context()
    ctx.api.get_activity_categories.return_value = {
        "activities": [{"steps": 1000}],
        "avg": {"steps": 900},
        "health": {"status": "ok"},
    }

    with patch("custom_components.kippy.coordinator.dt_util.now"):
        coord = KippyActivityCategoriesDataUpdateCoordinator(ctx, pet_ids=[1])
        coord.async_set_updated_data = MagicMock()

        await coord.async_refresh_pet(1)

        coord.async_set_updated_data.assert_called_once()
        new_data = coord.async_set_updated_data.call_args[0][0]
        assert new_data[1]["avg"]["steps"] == 900

    coord.data = {
        1: {
            "activities": [{"steps": 1000}],
            "avg": {"steps": 900},
            "health": {"status": "ok"},
        }
    }
    assert coord.get_activities(1) == [{"steps": 1000}]
    assert coord.get_avg(1) == {"steps": 900}
    assert coord.get_health(1) == {"status": "ok"}
    assert coord.get_activities(99) is None


# --- TEST 11: Map coordinator refresh interval setters ---
@pytest.mark.asyncio
async def test_map_coordinator_refresh_setters():
    """Test idle and live refresh setters adjust the update interval."""
    ctx = get_mock_context()
    coord = KippyMapDataUpdateCoordinator(ctx, kippy_id=123)

    coord.data = {"operating_status": OPERATING_STATUS_MAP[OPERATING_STATUS.IDLE]}
    await coord.async_set_idle_refresh(120)
    assert coord.idle_refresh == 120
    assert coord.update_interval == timedelta(seconds=120)

    coord.data = {"operating_status": OPERATING_STATUS_MAP[OPERATING_STATUS.LIVE]}
    await coord.async_set_live_refresh(5)
    assert coord.live_refresh == 5
    assert coord.update_interval == timedelta(seconds=5)


# --- TEST 12: Map coordinator ignores LBS updates ---
@pytest.mark.asyncio
async def test_map_coordinator_ignores_lbs():
    """Test that LBS updates are ignored when a location already exists."""
    from custom_components.kippy.const import LOCALIZATION_TECHNOLOGY_LBS

    ctx = get_mock_context()
    coord = KippyMapDataUpdateCoordinator(ctx, kippy_id=123)
    coord.ignore_lbs = True
    coord.data = {"gps_latitude": 1.0, "gps_longitude": 2.0}

    ctx.api.kippymap_action.return_value = {
        "localization_technology": LOCALIZATION_TECHNOLOGY_LBS,
        "gps_latitude": 9.0,
        "gps_longitude": 9.0,
        "operating_status": OPERATING_STATUS.IDLE,
    }

    data = await coord._async_update_data()
    assert data["gps_latitude"] == 1.0
    assert data["gps_longitude"] == 2.0


# --- TEST 13: Map coordinator accepts LBS when location unknown ---
@pytest.mark.asyncio
async def test_map_coordinator_accepts_lbs_when_unknown():
    """Test that LBS updates are accepted when no location is known yet."""
    from custom_components.kippy.const import LOCALIZATION_TECHNOLOGY_LBS

    ctx = get_mock_context()
    coord = KippyMapDataUpdateCoordinator(ctx, kippy_id=123)
    coord.ignore_lbs = True
    coord.data = None

    ctx.api.kippymap_action.return_value = {
        "localization_technology": LOCALIZATION_TECHNOLOGY_LBS,
        "gps_latitude": 9.0,
        "gps_longitude": 9.0,
        "operating_status": OPERATING_STATUS.IDLE,
    }

    data = await coord._async_update_data()
    assert data["gps_latitude"] == 9.0
