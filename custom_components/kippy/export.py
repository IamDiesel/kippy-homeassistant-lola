"""Builders for exporting Kippy GPS history to interoperable file formats."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape, quoteattr

GEOJSON_TRACK = "geojson_track"
GEOJSON_POINTS = "geojson_points"
GPX = "gpx"

EXPORT_FORMATS = (GEOJSON_TRACK, GEOJSON_POINTS, GPX)
DEFAULT_EXPORT_FORMATS = (GEOJSON_TRACK,)

#: Waypoints reported with a worse accuracy radius than this are dropped.
MAX_ACCURACY_RADIUS = 100

GPX_CREATOR = "kippy-homeassistant"


def normalize_timestamp(value: Any) -> str | None:
    """Return ``value`` as an ISO 8601 UTC timestamp, or ``None``.

    The API returns timestamps such as ``2026-08-11T23:33:12.111323758+00:00``.
    :func:`datetime.fromisoformat` accepts at most six fractional digits, so the
    fraction is truncated before parsing.
    """

    if not isinstance(value, str) or not value:
        return None

    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    # Split off the timezone suffix so the fraction can be truncated safely.
    tz_index = max(text.rfind("+"), text.rfind("-"))
    tz_suffix = ""
    if tz_index > 10:  # Ignore the dashes inside the date part.
        tz_suffix = text[tz_index:]
        text = text[:tz_index]

    if "." in text:
        base, fraction = text.split(".", 1)
        text = f"{base}.{fraction[:6]}"

    try:
        parsed = datetime.fromisoformat(f"{text}{tz_suffix}")
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def filter_positions(positions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return usable waypoints, oldest first.

    Standby pings and waypoints without coordinates or with a poor accuracy are
    dropped. Waypoints carrying a timestamp are sorted chronologically; if none
    of them do, the API order is reversed instead, since the API returns the
    newest waypoint first.
    """

    waypoints: list[dict[str, Any]] = []

    for position in positions:
        if position.get("positionType") == "SKIP" or position.get("isSkip"):
            continue

        lat = position.get("lat")
        lng = position.get("lng")
        if lat is None or lng is None:
            continue

        # ``radius`` may be present but null, so a dict default is not enough.
        radius = position.get("radius")
        if radius is None:
            radius = MAX_ACCURACY_RADIUS + 1
        if radius > MAX_ACCURACY_RADIUS:
            continue

        waypoints.append(
            {
                "lat": lat,
                "lng": lng,
                "radius": radius,
                "precision": position.get("precision"),
                "position_type": position.get("positionType"),
                "date": position.get("date"),
                "time": normalize_timestamp(position.get("date")),
            }
        )

    if any(waypoint["time"] for waypoint in waypoints):
        waypoints.sort(key=lambda waypoint: waypoint["time"] or "")
    else:
        waypoints.reverse()

    return waypoints


def build_geojson_track(
    waypoints: list[dict[str, Any]], pet_name: str
) -> dict[str, Any]:
    """Return a single ``LineString`` feature with per-point timestamps.

    A GeoJSON position holds no time, so the timestamps are carried in
    ``properties.coordinateProperties.times``, parallel to ``coordinates``. That
    is the convention used by GPSBabel and togeojson, and it keeps the route a
    single line for viewers that ignore the timestamps.
    """

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    # GeoJSON expects [longitude, latitude].
                    "coordinates": [[w["lng"], w["lat"]] for w in waypoints],
                },
                "properties": {
                    "name": f"{pet_name} Route",
                    "stroke": "#FF0000",
                    "stroke-width": 4,
                    "coordinateProperties": {
                        "times": [w["time"] for w in waypoints],
                    },
                },
            }
        ],
    }


def build_geojson_points(
    waypoints: list[dict[str, Any]], pet_name: str
) -> dict[str, Any]:
    """Return one ``Point`` feature per waypoint, with all attributes kept."""

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [w["lng"], w["lat"]]},
                "properties": {
                    "name": pet_name,
                    "sequence": index,
                    "time": w["time"],
                    "date": w["date"],
                    "radius": w["radius"],
                    "precision": w["precision"],
                    "positionType": w["position_type"],
                },
            }
            for index, w in enumerate(waypoints)
        ],
    }


def build_gpx(waypoints: list[dict[str, Any]], pet_name: str) -> str:
    """Return a GPX 1.1 track, the native format for timestamped tracks."""

    track_name = f"{pet_name} Route"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<gpx version="1.1" creator={quoteattr(GPX_CREATOR)} '
            'xmlns="http://www.topografix.com/GPX/1/1" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 '
            'http://www.topografix.com/GPX/1/1/gpx.xsd">'
        ),
        "  <metadata>",
        f"    <name>{escape(track_name)}</name>",
        "  </metadata>",
        "  <trk>",
        f"    <name>{escape(track_name)}</name>",
        "    <trkseg>",
    ]

    for waypoint in waypoints:
        lines.append(f'      <trkpt lat="{waypoint["lat"]}" lon="{waypoint["lng"]}">')
        if waypoint["time"]:
            lines.append(f"        <time>{waypoint['time']}</time>")
        lines.append("      </trkpt>")

    lines += ["    </trkseg>", "  </trk>", "</gpx>", ""]

    return "\n".join(lines)
