"""Concrete API client composed of endpoint mixins."""

from __future__ import annotations

from .activity import ActivityEndpoint
from .history import HistoryEndpoint
from .kippymap import KippyMapEndpoint
from .pets import PetsEndpoint
from .settings import SettingsEndpoint

__all__ = ["KippyApi"]


class KippyApi(
    ActivityEndpoint,
    SettingsEndpoint,
    KippyMapEndpoint,
    PetsEndpoint,
    HistoryEndpoint,  # <--- Hier fügen wir das neue Mixin hinzu!
):
    """Full-featured Kippy API client used by the integration."""
