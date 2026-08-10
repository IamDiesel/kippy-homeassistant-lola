"""Tests for Kippy services."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kippy.const import DOMAIN


@pytest.mark.asyncio
async def test_export_history_service(hass, enable_custom_integrations) -> None:
    """Test exporting history to GeoJSON service."""
    api = AsyncMock()
    api.get_pet_kippy_list = AsyncMock(
        return_value=[
            {
                "petID": 1,
                "petName": "Lola",
                "kippyID": 123,
                # Ensure coordinators are built and service is registered
                "expired_days": -5,
            }
        ]
    )
    api.kippymap_action = AsyncMock(return_value={})
    api.get_activity_categories = AsyncMock(return_value={})

    # Mocking historical positions
    api.get_positions_history = AsyncMock(
        return_value=[
            {"lat": 1.0, "lng": 2.0, "radius": 10},  # Valid waypoint
            {"positionType": "SKIP"},  # Should be skipped
            {
                "lat": 3.0,
                "lng": 4.0,
                "radius": 200,
            },  # Should be skipped (accuracy > 100)
            {"lat": None, "lng": 2.0},  # Should be skipped (missing lat)
        ]
    )

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_EMAIL: "a", CONF_PASSWORD: "b"})
    entry.add_to_hass(hass)

    with (
        patch("custom_components.kippy.aiohttp_client.async_get_clientsession"),
        patch("custom_components.kippy.KippyApi.async_create", return_value=api),
    ):
        setup_result = await hass.config_entries.async_setup(entry.entry_id)
        assert setup_result is True, "Integration setup failed"
        await hass.async_block_till_done()

    # Call the service and mock file operations
    with patch("os.makedirs"), patch("builtins.open"):
        await hass.services.async_call(
            DOMAIN,
            "export_history",
            {"pet_id": "1", "from_date": "2026-08-01", "to_date": "2026-08-10"},
            blocking=True,
        )

    # Ensure the API was called to fetch the history
    api.get_positions_history.assert_called_once_with("1", "2026-08-01", "2026-08-10")
