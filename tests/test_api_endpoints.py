"""Tests for the Kippy GraphQL API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.kippy.api.client import KippyApi
from custom_components.kippy.const import APP_ACTION


@pytest.fixture
def mock_api():
    """Create a KippyApi instance with a mocked GraphQL executor."""
    api = KippyApi(MagicMock())
    # We intercept execute_graphql so no real HTTP requests are sent
    api.execute_graphql = AsyncMock()
    return api


# --- TEST: pets.py ---
@pytest.mark.asyncio
async def test_get_pet_kippy_list(mock_api):
    """Test fetching the pet list and device info."""
    mock_api.execute_graphql.side_effect = [
        # 1. Aufruf: Tiere abrufen
        {"getPets": {"pets": [{"id": "1", "name": "Lola", "species": "CAT"}]}},
        # 2. Aufruf: Geräte-Infos abrufen
        {
            "getProducts": {
                "products": [
                    {
                        "id": "123",
                        "entityType": "PETLINK_GPS",  # Kippy filtert nach diesem Typ
                        "deviceType": "CAT",
                        "subscriptionIsActive": True,
                    }
                ]
            }
        },
        # 3. Aufruf: Einstellungen (Settings) des Geräts abrufen
        {
            "getPetlinkGps": {
                "petlinkGps": {
                    "settings": {"updateFrequency": 15, "enableGpsOnDefault": True}
                }
            }
        },
    ]

    pets = await mock_api.get_pet_kippy_list()
    # Der Aufruf-Zähler muss nun auf 3 stehen
    assert mock_api.execute_graphql.call_count == 3
    assert isinstance(pets, list)
    assert len(pets) > 0


@pytest.mark.asyncio
async def test_get_pet_kippy_list_empty(mock_api):
    """Test fetching the pet list when no pets exist."""
    mock_api.execute_graphql.return_value = {"getPets": {"pets": []}}

    pets = await mock_api.get_pet_kippy_list()
    assert pets == []


# --- TEST: kippymap.py ---
@pytest.mark.asyncio
async def test_kippymap_action_passive(mock_api):
    """Test getting the map location passively."""
    mock_api.execute_graphql.return_value = {
        "getPetlinkGps": {
            "petlinkGps": {
                "lastKnownPosition": {"lat": 1.0, "lng": 2.0},
                "lastKnownStatus": {"battery": 80},
            }
        }
    }

    result = await mock_api.kippymap_action(123)
    # THe API performs 3 calls: Status -> Wakeup -> Status
    assert mock_api.execute_graphql.call_count == 3
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_kippymap_action_active(mock_api):
    """Test triggering an active command (e.g., live tracking)."""
    mock_api.execute_graphql.return_value = {}

    result = await mock_api.kippymap_action(
        123, app_action=APP_ACTION.TURN_LIVE_TRACKING_ON
    )

    # Active actions trigger 4 API calls: Status -> Wakeup -> Action -> Status
    assert mock_api.execute_graphql.call_count == 4
    assert isinstance(result, dict)


# --- TEST: activity.py ---
@pytest.mark.asyncio
async def test_get_activity_categories(mock_api):
    """Test retrieving activities."""
    mock_api.execute_graphql.return_value = {
        "getActivitiesCat": {"activities": [{"date": "2026-08-10", "steps": 1000}]}
    }

    result = await mock_api.get_activity_categories(
        "1", "2026-08-01", "2026-08-10", 2, 1
    )
    mock_api.execute_graphql.assert_called_once()
    assert isinstance(result, dict)


# --- TEST: settings.py ---
@pytest.mark.asyncio
async def test_modify_kippy_settings(mock_api):
    """Test modifying various device settings triggers mutations."""
    mock_api.execute_graphql.return_value = {"sendSetting": {}}

    result = await mock_api.modify_kippy_settings(
        "123", update_frequency=15, gps_on_default=True, energy_saving_mode=False
    )

    # Update interval and GPS defualt are combined in a single payload,
    #  while energy saving is a separate mutation.
    # (1x Settings, 1x Energy Saving)
    assert mock_api.execute_graphql.call_count == 2
    assert isinstance(result, dict)
