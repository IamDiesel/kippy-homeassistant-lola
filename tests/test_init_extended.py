from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kippy import (
    _async_build_map_coordinators,
    async_setup_entry,
)
from custom_components.kippy.const import DOMAIN
from custom_components.kippy.coordinator import CoordinatorContext


@pytest.mark.asyncio
async def test_async_setup_entry_missing_data(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    assert await async_setup_entry(hass, entry) is False


@pytest.mark.asyncio
async def test_async_setup_entry_auth_failed(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_EMAIL: "a", CONF_PASSWORD: "b"})

    err = ClientResponseError(request_info=MagicMock(), history=())
    err.status = 401

    with (
        patch("custom_components.kippy.aiohttp_client.async_get_clientsession"),
        patch("custom_components.kippy.KippyApi.async_create") as create,
    ):
        api = AsyncMock()
        create.return_value = api
        api.login.side_effect = err

        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_setup_entry_not_ready(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_EMAIL: "a", CONF_PASSWORD: "b"})

    with (
        patch("custom_components.kippy.aiohttp_client.async_get_clientsession"),
        patch("custom_components.kippy.KippyApi.async_create") as create,
    ):
        api = AsyncMock()
        create.return_value = api
        api.login.side_effect = ClientError()

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_options_updated(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_EMAIL: "a", CONF_PASSWORD: "b"})

    with (
        patch("custom_components.kippy.aiohttp_client.async_get_clientsession"),
        patch(
            "custom_components.kippy.KippyApi.async_create", return_value=AsyncMock()
        ),
        patch("custom_components.kippy.ActivityRefreshTimer"),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        mock_coord = AsyncMock()
        mock_coord.data = {}
        with (
            patch(
                "custom_components.kippy.KippyDataUpdateCoordinator",
                return_value=mock_coord,
            ),
            patch(
                "custom_components.kippy.KippyMapDataUpdateCoordinator",
                return_value=AsyncMock(),
            ),
            patch(
                "custom_components.kippy.KippyActivityCategoriesDataUpdateCoordinator",
                return_value=AsyncMock(),
            ),
        ):
            await async_setup_entry(hass, entry)

            # Manually invoke the listener
            listeners = entry.update_listeners
        assert len(listeners) == 1

        # Call it
        await listeners[0](hass, entry)
        # Should call set_update_interval_minutes on coordinator
        entry.runtime_data.coordinator.set_update_interval_minutes.assert_called()

        # Call with no runtime_data
        entry.runtime_data = None
        await listeners[0](hass, entry)  # Should return without error


@pytest.mark.asyncio
async def test_on_new_pets_reload(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_EMAIL: "a", CONF_PASSWORD: "b"})

    with (
        patch("custom_components.kippy.aiohttp_client.async_get_clientsession"),
        patch(
            "custom_components.kippy.KippyApi.async_create", return_value=AsyncMock()
        ),
        patch("custom_components.kippy.ActivityRefreshTimer"),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        mock_coord = AsyncMock()
        mock_coord.data = {}
        with (
            patch(
                "custom_components.kippy.KippyDataUpdateCoordinator",
                return_value=mock_coord,
            ) as mock_coord_class,
            patch(
                "custom_components.kippy.KippyMapDataUpdateCoordinator",
                return_value=AsyncMock(),
            ),
            patch(
                "custom_components.kippy.KippyActivityCategoriesDataUpdateCoordinator",
                return_value=AsyncMock(),
            ),
        ):
            await async_setup_entry(hass, entry)
            on_new_pets = mock_coord_class.call_args.kwargs["on_new_pets"]

        with patch.object(
            hass.config_entries, "async_reload", AsyncMock()
        ) as mock_reload:
            entry.mock_state(hass, ConfigEntryState.LOADED)
            await on_new_pets()
            mock_reload.assert_called_once_with(entry.entry_id)

            mock_reload.reset_mock()
            entry.mock_state(hass, ConfigEntryState.NOT_LOADED)
            await on_new_pets()
            mock_reload.assert_not_called()


@pytest.mark.asyncio
async def test_build_map_coordinators_skips_invalid(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    api = AsyncMock()
    context = CoordinatorContext(hass, entry, api)

    coordinator = MagicMock()
    coordinator.data = {
        "pets": [
            {"petID": 1, "expired_days": 10, "kippyID": 1},
            {"subscription": {"status": "Active"}, "kippyID": 2},  # missing petID
        ]
    }

    maps, active = await _async_build_map_coordinators(context, coordinator)
    assert maps == {}
    assert active == []
