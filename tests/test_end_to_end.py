"""End-to-end tests for the Kippy integration."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kippy.const import DOMAIN, OPERATING_STATUS


@pytest.mark.asyncio
async def test_pet_setup_end_to_end(hass, enable_custom_integrations) -> None:
    """Test full integration setup and verify sensor states."""
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    ts = int(today.timestamp())

    # Mock API data for one pet
    pets = [
        {
            "petID": 1,
            "petName": "Lola",
            "kippyID": 123,
            "kippyIMEI": "ABC",
            "expired_days": -5,
            "petKind": "3",  # Cat
        }
    ]

    map_data = {
        "battery": 80,
        "localization_technology": "GPS",
        "contact_time": ts,
        "fix_time": ts - 1,
        "gps_time": ts - 2,
        "lbs_time": ts - 3,
        "gps_latitude": 1.0,
        "gps_longitude": 2.0,
        "gps_accuracy": 3,
        "gps_altitude": 4,
        "operating_status": OPERATING_STATUS.IDLE,
    }

    activity_data = {
        "activities": [
            {
                "date": today_str,
                "steps": 1000,
                "calories": 200,
                "run": 10,
                "walk": 20,
                "sleep": 30,
                "rest": 40,
                "play": 50,
                "relax": 60,
                "jumps": 70,
                "climb": 80,
                "grooming": 90,
                "eat": 100,
                "drink": 110,
            }
        ]
    }

    # Setup API Mock
    api = AsyncMock()
    api.login = AsyncMock()
    api.get_pet_kippy_list = AsyncMock(return_value=pets)
    api.kippymap_action = AsyncMock(return_value=map_data)
    api.get_activity_categories = AsyncMock(return_value=activity_data)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_EMAIL: "a", CONF_PASSWORD: "b"})
    entry.add_to_hass(hass)

    with (
        patch("custom_components.kippy.aiohttp_client.async_get_clientsession"),
        patch("custom_components.kippy.KippyApi.async_create", return_value=api),
        patch("custom_components.kippy.coordinator.dt_util.now", return_value=today),
    ):
        # Boot up the integration
        setup_result = await hass.config_entries.async_setup(entry.entry_id)
        assert setup_result is True, "Integration setup failed"
        await hass.async_block_till_done()

    # --- Verify Sensor States ---
    # Home Assistant generates entity IDs based on the device name.
    # "Kippy Lola" -> sensor.kippy_lola_...

    # Battery
    state = hass.states.get("sensor.kippy_lola_battery_level")
    assert state is not None, "Battery sensor not found"
    assert state.state == "80"

    # Steps
    state = hass.states.get("sensor.kippy_lola_steps")
    assert state is not None, "Steps sensor not found"
    assert state.state == "1000"

    # Pet Type
    state = hass.states.get("sensor.kippy_lola_pet_type")
    assert state is not None, "Pet type sensor not found"
    assert state.state == "cat"

    # --- Verify Device Tracker ---
    tracker = hass.states.get("device_tracker.kippy_lola")
    assert tracker is not None, "Device tracker not found"
    assert tracker.attributes.get("battery") == 80
    assert tracker.attributes.get("latitude") == 1.0
    assert tracker.attributes.get("longitude") == 2.0
