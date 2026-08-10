"""API endpoint for fetching Kippy Map location data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ._base import BaseKippyApi

GET_PETLINK_GPS_QUERY = """
query getPetlinkGps($id: String!) {
  getPetlinkGps(id: $id) {
    petlinkGps {
      lastKnownPosition {
        lat
        lng
        alt
        radius
        positionType
        date
      }
      lastKnownStatus {
        battery
        liveTracking
        energySavingMode
        date
      }
    }
  }
}
"""

SEND_COMMAND_MUTATION = """
mutation sendCommand($command: Command!) {
  sendCommand(command: $command) {
    code
    message
  }
}
"""

APP_KEEP_ALIVE_MUTATION = """
mutation appKeepAlive($productIds: [String!]!) {
  appKeepAlive(productIds: $productIds) {
    code
    message
  }
}
"""


class KippyMapEndpoint(BaseKippyApi):
    """Mixin implementing the Kippy Map action endpoint."""

    def _parse_iso_timestamp(self, iso_str: str | None) -> int | None:
        if not iso_str:
            return None
        try:
            if "." in iso_str:
                base, fraction = iso_str.split(".", 1)
                if "+" in fraction:
                    frac, tz = fraction.split("+", 1)
                    iso_str = f"{base}.{frac[:6]}+{tz}"
                elif "-" in fraction:
                    frac, tz = fraction.split("-", 1)
                    iso_str = f"{base}.{frac[:6]}-{tz}"
                else:
                    iso_str = f"{base}.{fraction[:6]}"
            dt = datetime.fromisoformat(iso_str)
            return int(dt.timestamp())
        except (ValueError, TypeError, AttributeError):
            return None

    async def kippymap_action(
        self,
        kippy_id: int | str,
        do_sms: bool = True,
        app_action: int | None = None,
        geofence_id: int | None = None,
    ) -> dict[str, Any]:
        # 1. Aktuellen Status passiv abfragen
        data = await self.execute_graphql(GET_PETLINK_GPS_QUERY, {"id": str(kippy_id)})
        petlink_gps = data.get("getPetlinkGps", {}).get("petlinkGps") or {}
        last_status = petlink_gps.get("lastKnownStatus") or {}
        live_tracking_state = last_status.get("liveTracking")

        command_sent = False

        # 2. Kommando & Keep-Alive Logik
        if app_action == 2:
            # START: Sende LIVE_TRACKING Befehl und Herzschlag
            await self.execute_graphql(
                SEND_COMMAND_MUTATION,
                {
                    "command": {
                        "commandType": "LIVE_TRACKING",
                        "id": str(kippy_id),
                        "modeType": "SENTINEL",
                    }
                },
            )
            await self.execute_graphql(
                APP_KEEP_ALIVE_MUTATION, {"productIds": [str(kippy_id)]}
            )
            command_sent = True

        elif app_action == 1:
            # STOP: Sende LIVE_TRACKING mit duration: 0 zum Beenden!
            await self.execute_graphql(
                SEND_COMMAND_MUTATION,
                {
                    "command": {
                        "commandType": "LIVE_TRACKING",
                        "id": str(kippy_id),
                        "duration": 0,
                        "modeType": "SENTINEL",
                    }
                },
            )
            command_sent = True

        else:
            # NORMALES POLLING
            if live_tracking_state in ("ON", "REQUESTED"):
                # Während Live-Tracking aktiv ist: Herzschlag aufrechterhalten
                await self.execute_graphql(
                    APP_KEEP_ALIVE_MUTATION, {"productIds": [str(kippy_id)]}
                )
            else:
                # Im Idle: Ganz normaler WAKEUP für periodische Updates
                await self.execute_graphql(
                    SEND_COMMAND_MUTATION,
                    {
                        "command": {
                            "commandType": "WAKEUP",
                            "id": str(kippy_id),
                            "modeType": "SENTINEL",
                        }
                    },
                )
                command_sent = True

        # 3. Wenn ein Befehl gesendet wurde, Daten sofort neu einlesen
        if command_sent:
            data = await self.execute_graphql(
                GET_PETLINK_GPS_QUERY, {"id": str(kippy_id)}
            )
            petlink_gps = data.get("getPetlinkGps", {}).get("petlinkGps") or {}
            last_status = petlink_gps.get("lastKnownStatus") or {}

        last_position = petlink_gps.get("lastKnownPosition") or {}
        live_tracking = last_status.get("liveTracking")
        energy_saving = last_status.get("energySavingMode")

        response: dict[str, Any] = {}

        lat = last_position.get("lat")
        if lat is not None:
            response["gps_latitude"] = lat

        lng = last_position.get("lng")
        if lng is not None:
            response["gps_longitude"] = lng

        radius = last_position.get("radius")
        if radius is not None:
            response["gps_accuracy"] = radius

        altitude = last_position.get("alt")
        if altitude is not None:
            response["gps_altitude"] = altitude

        tech = last_position.get("positionType")
        if tech == "WIFI":
            response["localization_technology"] = "Wifi"
        elif tech == "GPS":
            response["localization_technology"] = "GPS"
        elif tech == "LBS":
            response["localization_technology"] = "LBS (Low accuracy)"
        else:
            response["localization_technology"] = str(tech).title() if tech else None

        battery = last_status.get("battery")
        if battery is not None:
            response["battery"] = battery

        response["fix_time"] = self._parse_iso_timestamp(last_position.get("date"))
        response["contact_time"] = self._parse_iso_timestamp(last_status.get("date"))

        # UI-Override für den Home Assistant Schalter
        if app_action == 2 and live_tracking not in ("ON", "REQUESTED"):
            live_tracking = "REQUESTED"
        elif app_action == 1:
            live_tracking = "OFF"

        if live_tracking == "ON":
            response["operating_status"] = 5
        elif live_tracking == "REQUESTED":
            response["operating_status"] = "starting_live"
        elif energy_saving == "ON":
            response["operating_status"] = 18
        else:
            response["operating_status"] = 1

        return response
