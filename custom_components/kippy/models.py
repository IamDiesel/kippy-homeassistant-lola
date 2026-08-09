"""Data models for the Kippy integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .api import KippyApi
from .coordinator import (
    ActivityRefreshTimer,
    KippyActivityCategoriesDataUpdateCoordinator,
    KippyDataUpdateCoordinator,
    KippyMapDataUpdateCoordinator,
)


@dataclass
class KippyData:
    """Data for the Kippy integration."""

    api: KippyApi
    coordinator: KippyDataUpdateCoordinator
    map_coordinators: dict[int | str, KippyMapDataUpdateCoordinator]
    activity_coordinator: KippyActivityCategoriesDataUpdateCoordinator
    activity_timers: dict[int | str, ActivityRefreshTimer]


type KippyConfigEntry = ConfigEntry[KippyData]
