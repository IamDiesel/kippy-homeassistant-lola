"""Modern core tests for the Kippy integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError, ClientResponseError
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kippy import async_setup_entry, async_unload_entry
from custom_components.kippy.api._utils import _redact
from custom_components.kippy.button import async_setup_entry as async_setup_button
from custom_components.kippy.config_flow import KippyConfigFlow
from custom_components.kippy.const import DOMAIN, PLATFORMS
from custom_components.kippy.device_tracker import (
    async_setup_entry as async_setup_tracker,
)
from custom_components.kippy.helpers import (
    normalize_device_update_interval,
    normalize_kippy_identifier,
)
from custom_components.kippy.sensor import async_setup_entry as async_setup_sensor
from custom_components.kippy.switch import async_setup_entry as async_setup_switch


# --- TEST 1: Helper ---
def test_normalize_kippy_identifier_invalid_values() -> None:
    """Non-numeric identifiers should be handled as strings now."""
    assert normalize_kippy_identifier({"kippyID": "abc"}) == "abc"


# --- TEST 2: Config Flow ---
@pytest.mark.asyncio
async def test_config_flow_success() -> None:
    """Successful login creates an entry."""
    flow = KippyConfigFlow()
    flow.hass = MagicMock()
    with (
        patch(
            "custom_components.kippy.config_flow.aiohttp_client.async_get_clientsession"
        ),
        patch("custom_components.kippy.config_flow.KippyApi.async_create") as create,
    ):
        api = AsyncMock()
        create.return_value = api
        api.login.return_value = None
        result = await flow.async_step_user({CONF_EMAIL: "user", CONF_PASSWORD: "pass"})

    assert result["type"].value == "create_entry"
    assert result["data"] == {CONF_EMAIL: "user", CONF_PASSWORD: "pass"}


# --- TEST 3: Init Setup & Unload ---
@pytest.mark.asyncio
async def test_async_setup_entry_success_and_unload(hass) -> None:
    """Successful setup stores data in runtime_data and unload removes it."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_EMAIL: "a", CONF_PASSWORD: "b"}, entry_id="1"
    )
    entry.add_to_hass(hass)

    api = AsyncMock()
    data_coord = AsyncMock()
    data_coord.data = {"pets": [{"petID": 1, "kippyID": 1}]}

    with (
        patch("custom_components.kippy.aiohttp_client.async_get_clientsession"),
        patch("custom_components.kippy.KippyApi.async_create", return_value=api),
        patch(
            "custom_components.kippy.KippyDataUpdateCoordinator",
            return_value=data_coord,
        ),
        patch(
            "custom_components.kippy.KippyMapDataUpdateCoordinator",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.kippy.KippyActivityCategoriesDataUpdateCoordinator",
            return_value=AsyncMock(),
        ),
        patch("custom_components.kippy.ActivityRefreshTimer"),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        patch.object(
            hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
        ) as mock_unload,
    ):
        result = await async_setup_entry(hass, entry)
        assert result is True

        assert entry.runtime_data is not None
        assert hasattr(entry.runtime_data, "coordinator")

        await async_unload_entry(hass, entry)
        mock_unload.assert_awaited_with(entry, PLATFORMS)


# --- TEST 4: Sensor Setup ---
@pytest.mark.asyncio
async def test_sensor_async_setup_entry_creates_entities() -> None:
    """async_setup_entry adds sensors using runtime_data object."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    coordinator.data = {"pets": [{"petID": 1}]}

    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: MagicMock()}
    mock_data.activity_coordinator = MagicMock()
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_sensor(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()
    assert len(async_add_entities.call_args[0][0]) > 0


# --- TEST 5: Tracker Setup ---
@pytest.mark.asyncio
async def test_device_tracker_async_setup_entry_creates_entities() -> None:
    """async_setup_entry adds trackers using runtime_data object."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    coordinator.data = {"pets": [{"petID": 1}]}

    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: MagicMock()}
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_tracker(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()
    assert len(async_add_entities.call_args[0][0]) > 0


# --- TEST 6: Config Flow Error handling ---
@pytest.mark.asyncio
async def test_config_flow_errors() -> None:
    """Test config flow handles unexpected errors gracefully."""
    flow = KippyConfigFlow()
    flow.hass = MagicMock()
    with (
        patch(
            "custom_components.kippy.config_flow.aiohttp_client.async_get_clientsession"
        ),
        patch("custom_components.kippy.config_flow.KippyApi.async_create") as create,
    ):
        api = AsyncMock()
        create.return_value = api
        # Simulation of connection loss or unexpected error
        api.login.side_effect = Exception("Connection lost")
        result = await flow.async_step_user({CONF_EMAIL: "user", CONF_PASSWORD: "pass"})

        # Flow must return as a form with an error message, not crash
        assert result["type"].value == "form"
    assert "base" in result["errors"]


# --- TEST 7: Switch Setup ---
@pytest.mark.asyncio
async def test_switch_async_setup_entry_creates_entities() -> None:
    """async_setup_entry adds switches using runtime_data object."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    coordinator.data = {"pets": [{"petID": 1}]}

    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: MagicMock()}
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_switch(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()
    assert len(async_add_entities.call_args[0][0]) > 0


# --- TEST 8: Button Setup ---
@pytest.mark.asyncio
async def test_button_async_setup_entry_creates_entities() -> None:
    """async_setup_entry adds buttons using runtime_data object."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "1"

    coordinator = MagicMock()
    coordinator.data = {"pets": [{"petID": 1}]}

    mock_data = MagicMock()
    mock_data.coordinator = coordinator
    mock_data.map_coordinators = {1: MagicMock()}
    mock_data.activity_coordinator = MagicMock()
    entry.runtime_data = mock_data

    async_add_entities = MagicMock()
    await async_setup_button(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()
    assert len(async_add_entities.call_args[0][0]) > 0


# --- TEST 9: Log Redaction (Logic) ---
def test_redact_handles_nested_fields() -> None:
    """Test that sensitive information like petID is correctly masked for logs."""
    payload = {"outer": {"app_code": "xyz", "list": [{"petID": "123"}]}}
    redacted = _redact(payload)
    assert redacted["outer"]["app_code"] == "***"
    assert redacted["outer"]["list"][0]["petID"] == "***"


# --- TEST 10: Interval Normalization (Logic) ---
def test_normalize_device_update_interval() -> None:
    """Normalize helper accepts valid values and rejects invalid ones."""
    # OK Values
    assert normalize_device_update_interval(15) == 15
    assert normalize_device_update_interval("30") == 30
    # NOK Values
    assert normalize_device_update_interval(None) is None
    assert normalize_device_update_interval(0) is None
    assert normalize_device_update_interval("abc") is None


# --- TEST 9: Config Flow Options ---
@pytest.mark.asyncio
async def test_options_flow() -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_EMAIL: "a", CONF_PASSWORD: "b"}, entry_id="1"
    )
    flow = KippyConfigFlow()
    options_flow = flow.async_get_options_flow(entry)

    # Initial step shows the form
    result = await options_flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    # User inputs a valid value
    result = await options_flow.async_step_init({"device_update_interval": 30})
    assert result["type"] == "create_entry"
    assert result["data"]["device_update_interval"] == 30

    # User inputs an invalid value
    result = await options_flow.async_step_init({"device_update_interval": "invalid"})
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_device_update_interval"}


# --- TEST 10: Config Flow Match ---
def test_is_matching() -> None:
    """Test is_matching."""
    flow = KippyConfigFlow()
    assert flow.is_matching(flow) is True
    assert flow.is_matching(None) is False


@pytest.mark.asyncio
async def test_config_flow_client_response_error_auth() -> None:
    """Test config flow ClientResponseError 401."""
    flow = KippyConfigFlow()
    flow.hass = MagicMock()
    with (
        patch(
            "custom_components.kippy.config_flow.aiohttp_client.async_get_clientsession"
        ),
        patch("custom_components.kippy.config_flow.KippyApi.async_create") as create,
    ):
        api = AsyncMock()
        create.return_value = api

        # We need to simulate a ClientResponseError properly.
        # Since it's a bit verbose to mock properly, we can just throw it.
        err = ClientResponseError(request_info=MagicMock(), history=())
        err.status = 401
        api.login.side_effect = err

        result = await flow.async_step_user({CONF_EMAIL: "user", CONF_PASSWORD: "pass"})
        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_config_flow_client_response_error_other() -> None:
    """Test config flow ClientResponseError other status."""
    flow = KippyConfigFlow()
    flow.hass = MagicMock()
    with (
        patch(
            "custom_components.kippy.config_flow.aiohttp_client.async_get_clientsession"
        ),
        patch("custom_components.kippy.config_flow.KippyApi.async_create") as create,
    ):
        api = AsyncMock()
        create.return_value = api
        err = ClientResponseError(request_info=MagicMock(), history=())
        err.status = 500
        api.login.side_effect = err

        result = await flow.async_step_user({CONF_EMAIL: "user", CONF_PASSWORD: "pass"})
        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_client_error() -> None:
    """Test config flow ClientError."""
    flow = KippyConfigFlow()
    flow.hass = MagicMock()
    with (
        patch(
            "custom_components.kippy.config_flow.aiohttp_client.async_get_clientsession"
        ),
        patch("custom_components.kippy.config_flow.KippyApi.async_create") as create,
    ):
        api = AsyncMock()
        create.return_value = api
        api.login.side_effect = ClientError("Test")

        result = await flow.async_step_user({CONF_EMAIL: "user", CONF_PASSWORD: "pass"})
        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_runtime_error() -> None:
    """Test config flow RuntimeError."""
    flow = KippyConfigFlow()
    flow.hass = MagicMock()
    with (
        patch(
            "custom_components.kippy.config_flow.aiohttp_client.async_get_clientsession"
        ),
        patch("custom_components.kippy.config_flow.KippyApi.async_create") as create,
    ):
        api = AsyncMock()
        create.return_value = api
        api.login.side_effect = RuntimeError("Test")

        result = await flow.async_step_user({CONF_EMAIL: "user", CONF_PASSWORD: "pass"})
        assert result["type"] == "form"
        assert result["errors"] == {"base": "unknown"}
