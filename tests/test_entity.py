"""Tests for Kippy base entities."""

from unittest.mock import MagicMock

from custom_components.kippy.entity import KippyMapEntity, KippyPetEntity


def test_kippy_pet_entity_device_info() -> None:
    """Test that the pet entity correctly formats device info for HA."""
    coordinator = MagicMock()
    pet = {"petID": 1, "petName": "Lola", "kippyID": 12345}

    entity = KippyPetEntity(coordinator, pet)
    device_info = entity.device_info

    # Verify the device name and identifier are mapped correctly
    assert device_info["name"] == "Kippy Lola"
    assert device_info["identifiers"] == {("kippy", "1")}


def test_kippy_map_entity_device_info() -> None:
    """Test that the map entity correctly formats device info for HA."""
    coordinator = MagicMock()
    pet = {"petID": 2, "petName": "Rex"}

    entity = KippyMapEntity(coordinator, pet)
    device_info = entity.device_info

    assert device_info["name"] == "Kippy Rex"
    assert device_info["identifiers"] == {("kippy", "2")}
