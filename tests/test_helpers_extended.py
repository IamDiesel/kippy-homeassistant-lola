"""Extended tests for Kippy helper utilities."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kippy.const import DEFAULT_DEVICE_UPDATE_INTERVAL_MINUTES, DOMAIN
from custom_components.kippy.helpers import (
    DEVICE_UPDATE_INTERVAL_KEY,
    MapRefreshSettings,
    _collect_refresh_updates,
    get_device_update_interval,
    update_pet_data,
)


def test_update_pet_data_preserves_fields() -> None:
    """Test update_pet_data preserves fields and returns current when missing."""
    pets = [
        {"petID": 1, "value": 1},
        {"petID": 2, "value": 2},
    ]
    current = {"petID": 2, "value": 3, "keep": True}

    updated = update_pet_data(pets, 2, current, preserve=("keep",))
    assert updated["value"] == 2
    assert updated["keep"] is True

    # Missing pet should return current
    missing = update_pet_data(pets, 3, current)
    assert missing is current


def test_get_device_update_interval() -> None:
    """Test retrieving device update intervals from config entry."""
    # Test default
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    assert get_device_update_interval(entry) == DEFAULT_DEVICE_UPDATE_INTERVAL_MINUTES

    # Test configured
    entry_configured = MockConfigEntry(
        domain=DOMAIN, data={}, options={DEVICE_UPDATE_INTERVAL_KEY: 30}
    )
    assert get_device_update_interval(entry_configured) == 30


def test_collect_refresh_updates() -> None:
    """Test normalization of string and integer refresh updates."""
    updates = _collect_refresh_updates("15", 20)
    assert updates["idle_seconds"] == 15
    assert updates["live_seconds"] == 20


def test_map_refresh_settings_dataclass() -> None:
    """Test MapRefreshSettings initialization."""
    settings = MapRefreshSettings(idle_seconds=600, live_seconds=20)
    assert settings.idle_seconds == 600
    assert settings.live_seconds == 20


def test_coerce_int() -> None:
    """Test coerce_int handles strings, ints, and invalid values."""
    from custom_components.kippy.helpers import coerce_int

    assert coerce_int("42") == 42
    assert coerce_int(7) == 7
    assert coerce_int("  9  ") == 9
    assert coerce_int("") is None
    assert coerce_int("   ") is None
    assert coerce_int("abc") is None
    assert coerce_int(None) is None


def test_normalize_device_update_interval_bounds() -> None:
    """Test normalize_device_update_interval enforces the allowed range."""
    from custom_components.kippy.helpers import normalize_device_update_interval

    assert normalize_device_update_interval("10") == 10
    assert normalize_device_update_interval(0) is None
    assert normalize_device_update_interval(100000) is None
    assert normalize_device_update_interval("nope") is None


def test_build_device_name() -> None:
    """Test build_device_name with and without a pet name."""
    from custom_components.kippy.helpers import build_device_name

    assert build_device_name({"petName": "Lola"}) == "Kippy Lola"
    assert build_device_name({}) == "Kippy"


def test_build_device_info_connections() -> None:
    """Test build_device_info includes identifiers and connections."""
    from custom_components.kippy.helpers import build_device_info

    pet = {
        "petName": "Lola",
        "kippyID": 123,
        "kippyIMEI": "imei123",
        "kippySerial": "serial123",
        "kippyType": "GPS",
        "kippyFirmware": "1.0",
    }
    info = build_device_info(1, pet)
    assert (DOMAIN, "1") in info["identifiers"]
    assert ("kippy_id", "123") in info["connections"]
    assert ("imei", "imei123") in info["connections"]
    assert ("serial", "serial123") in info["connections"]
    assert info["name"] == "Kippy Lola"
    assert info["serial_number"] == "serial123"


def test_is_pet_subscription_active() -> None:
    """Test subscription active detection with different expired_days values."""
    from custom_components.kippy.helpers import is_pet_subscription_active

    assert is_pet_subscription_active({"expired_days": -5}) is True
    assert is_pet_subscription_active({"expired_days": 5}) is False
    assert is_pet_subscription_active({"expired_days": "invalid"}) is True
    assert is_pet_subscription_active({}) is True


def test_normalize_kippy_identifier_variants() -> None:
    """Test normalize_kippy_identifier for different identifier types."""
    from custom_components.kippy.helpers import normalize_kippy_identifier

    assert normalize_kippy_identifier({"kippyID": 123}) == 123
    assert normalize_kippy_identifier({"kippy_id": "456"}) == 456
    assert normalize_kippy_identifier({"kippyID": "abc"}) == "abc"
    assert normalize_kippy_identifier({}) is None
    assert normalize_kippy_identifier({"petID": 7}, include_pet_id=True) == 7
    assert normalize_kippy_identifier({"kippyID": [1]}) == "[1]"


def test_get_map_refresh_settings() -> None:
    """Test reading map refresh settings from config entry options."""
    from custom_components.kippy.helpers import (
        MAP_REFRESH_OPTIONS_KEY,
        get_map_refresh_settings,
    )

    # No options
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    assert get_map_refresh_settings(entry, 1) is None

    # Pet without options
    entry2 = MockConfigEntry(
        domain=DOMAIN, data={}, options={MAP_REFRESH_OPTIONS_KEY: {}}
    )
    assert get_map_refresh_settings(entry2, 1) is None

    # Valid options
    entry3 = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            MAP_REFRESH_OPTIONS_KEY: {
                "1": {"idle_seconds": 600, "live_seconds": 20},
            }
        },
    )
    settings = get_map_refresh_settings(entry3, 1)
    assert settings is not None
    assert settings.idle_seconds == 600
    assert settings.live_seconds == 20

    # Invalid values -> None
    entry4 = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={MAP_REFRESH_OPTIONS_KEY: {"1": {"idle_seconds": 0}}},
    )
    assert get_map_refresh_settings(entry4, 1) is None


async def test_async_update_device_update_interval(hass) -> None:
    """Test updating the device update interval on the config entry."""
    from custom_components.kippy.helpers import async_update_device_update_interval

    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    await async_update_device_update_interval(hass, entry, 30)
    assert entry.options[DEVICE_UPDATE_INTERVAL_KEY] == 30

    # Setting the same value should not raise and keep the value
    await async_update_device_update_interval(hass, entry, 30)
    assert entry.options[DEVICE_UPDATE_INTERVAL_KEY] == 30


async def test_async_update_map_refresh_settings(hass) -> None:
    """Test updating map refresh settings on the config entry."""
    from custom_components.kippy.helpers import (
        MAP_REFRESH_OPTIONS_KEY,
        async_update_map_refresh_settings,
    )

    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    # No updates when both values are None
    await async_update_map_refresh_settings(hass, entry, 1)
    assert MAP_REFRESH_OPTIONS_KEY not in entry.options

    # Update idle and live seconds
    await async_update_map_refresh_settings(
        hass, entry, 1, idle_seconds=600, live_seconds=20
    )
    stored = entry.options[MAP_REFRESH_OPTIONS_KEY]["1"]
    assert stored["idle_seconds"] == 600
    assert stored["live_seconds"] == 20

    # Applying the same values again should not change anything
    await async_update_map_refresh_settings(
        hass, entry, 1, idle_seconds=600, live_seconds=20
    )
    stored = entry.options[MAP_REFRESH_OPTIONS_KEY]["1"]
    assert stored["idle_seconds"] == 600
