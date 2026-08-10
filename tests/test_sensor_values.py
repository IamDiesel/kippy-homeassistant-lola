"""Unit tests for Kippy sensor value logic."""

from unittest.mock import MagicMock

from custom_components.kippy.sensor import (
    KippyBatterySensor,
    KippyEnergySavingStatusSensor,
    KippyExpiredDaysSensor,
    KippyIDSensor,
    KippyIMEISensor,
    KippyLastContactSensor,
    KippyNextContactSensor,
    KippyPetTypeSensor,
    KippyStepsSensor,
)


def _make_pet() -> dict:
    """Return a minimal pet payload used across the tests."""
    return {"petID": 1, "petName": "Lola", "kippyID": 123}


def test_expired_days_sensor_values() -> None:
    """Test the expired days sensor reports remaining days or expired label."""
    from custom_components.kippy.const import LABEL_EXPIRED

    coordinator = MagicMock()
    pet = _make_pet()

    sensor = KippyExpiredDaysSensor(coordinator, pet)
    sensor.hass = None

    # No data yet
    pet["expired_days"] = None
    assert sensor.native_value is None

    # Invalid value
    pet["expired_days"] = "abc"
    assert sensor.native_value is None
    assert sensor.native_unit_of_measurement is None

    # Expired subscription
    pet["expired_days"] = 5
    assert sensor.native_value == LABEL_EXPIRED
    assert sensor.native_unit_of_measurement is None

    # Active subscription with remaining days
    pet["expired_days"] = -10
    assert sensor.native_value == 10


def test_pet_type_sensor() -> None:
    """Test the pet type sensor maps petKind to a readable type."""
    from custom_components.kippy.const import PET_KIND_TO_TYPE

    coordinator = MagicMock()
    pet = _make_pet()
    sensor = KippyPetTypeSensor(coordinator, pet)

    known_kind = next(iter(PET_KIND_TO_TYPE))
    pet["petKind"] = known_kind
    assert sensor.native_value == PET_KIND_TO_TYPE[known_kind]

    pet["petKind"] = "unknown_kind"
    assert sensor.native_value is None


def test_id_and_imei_sensors() -> None:
    """Test the diagnostic ID and IMEI sensors."""
    coordinator = MagicMock()
    pet = _make_pet()

    id_sensor = KippyIDSensor(coordinator, pet)
    assert id_sensor.native_value == 123

    pet["kippyIMEI"] = "imei123"
    imei_sensor = KippyIMEISensor(coordinator, pet)
    assert imei_sensor.native_value == "imei123"


def test_battery_sensor_values() -> None:
    """Test the battery sensor reads from map data with pet fallback."""
    coordinator = MagicMock()
    pet = _make_pet()

    coordinator.data = {"battery": 80}
    sensor = KippyBatterySensor(coordinator, pet)
    assert sensor.native_value == 80

    # Falls back to pet data when map data is missing
    coordinator.data = {}
    pet["batteryLevel"] = 55
    assert sensor.native_value == 55

    # Invalid value
    coordinator.data = {"battery": "n/a"}
    assert sensor.native_value is None


def test_energy_saving_status_sensor() -> None:
    """Test the energy saving status sensor handles pending and active states."""
    coordinator = MagicMock()
    pet = _make_pet()
    sensor = KippyEnergySavingStatusSensor(coordinator, pet)

    pet["energySavingMode"] = 1
    pet["energySavingModePending"] = False
    assert sensor.native_value == "on"

    pet["energySavingMode"] = 0
    assert sensor.native_value == "off"

    pet["energySavingModePending"] = True
    assert sensor.native_value == "off_pending"

    pet["energySavingMode"] = 1
    assert sensor.native_value == "on_pending"


def test_last_contact_sensor() -> None:
    """Test the last contact sensor converts a timestamp to a datetime."""
    coordinator = MagicMock()
    pet = _make_pet()
    sensor = KippyLastContactSensor(coordinator, pet)

    coordinator.data = {"contact_time": 1786363200}
    value = sensor.native_value
    assert value is not None
    assert value.year == 2026

    coordinator.data = {"contact_time": "invalid"}
    assert sensor.native_value is None

    coordinator.data = None
    assert sensor.native_value is None


def test_next_contact_sensor() -> None:
    """Test the next contact sensor combines contact time and frequency."""
    coordinator = MagicMock()
    base_coordinator = MagicMock()
    base_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    pet = _make_pet()

    sensor = KippyNextContactSensor(coordinator, base_coordinator, pet)

    # Missing frequency -> None
    coordinator.data = {"contact_time": 1786363200}
    pet.pop("updateFrequency", None)
    assert sensor.native_value is None

    # Valid data -> future datetime
    pet["updateFrequency"] = 1
    value = sensor.native_value
    assert value is not None

    # Invalid data -> None
    coordinator.data = {"contact_time": "bad"}
    assert sensor.native_value is None


def test_steps_sensor_grouped_activities() -> None:
    """Test the steps sensor sums grouped activity data for today."""
    from homeassistant.util import dt as dt_util

    coordinator = MagicMock()
    pet = _make_pet()
    sensor = KippyStepsSensor(coordinator, pet)
    sensor.hass = None

    today_prefix = dt_util.now().strftime("%Y%m%d")
    coordinator.get_activities.return_value = [
        {
            "activity": "steps",
            "data": [
                {"timeCaption": f"{today_prefix}0800", "value": 400},
                {"timeCaption": f"{today_prefix}0900", "value": 600},
                {"timeCaption": "20000101", "value": 999},
            ],
        }
    ]

    assert sensor.native_value == 1000


def test_steps_sensor_no_activities() -> None:
    """Test the steps sensor returns None when there is no activity data."""
    coordinator = MagicMock()
    pet = _make_pet()
    sensor = KippyStepsSensor(coordinator, pet)

    coordinator.get_activities.return_value = None
    assert sensor.native_value is None
