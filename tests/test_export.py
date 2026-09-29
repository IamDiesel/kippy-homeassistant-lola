"""Tests for the history export builders."""

from custom_components.kippy.export import (
    build_geojson_points,
    build_geojson_track,
    build_gpx,
    filter_positions,
    normalize_timestamp,
)

RAW_POSITIONS = [
    # Newest first, as returned by the API.
    {
        "lat": 3.0,
        "lng": 4.0,
        "radius": 20,
        "precision": "HIGH",
        "positionType": "GPS",
        "date": "2026-08-08T12:00:00.123456789+00:00",
    },
    {
        "lat": 1.0,
        "lng": 2.0,
        "radius": 10,
        "precision": "HIGH",
        "positionType": "WIFI",
        "date": "2026-08-08T10:00:00.000Z",
    },
    {"positionType": "SKIP", "lat": 9.0, "lng": 9.0, "radius": 5},
    {"lat": 5.0, "lng": 6.0, "radius": 5, "isSkip": True},
    {"lat": 7.0, "lng": 8.0, "radius": 200},  # accuracy too poor
    {"lat": None, "lng": 2.0, "radius": 5},  # no coordinates
    {"lat": 8.0, "lng": 9.0, "radius": None},  # null radius must not raise
]


def test_normalize_timestamp() -> None:
    """Timestamps are normalized to whole seconds in UTC."""
    assert (
        normalize_timestamp("2026-08-11T23:33:12.111323758+00:00")
        == "2026-08-11T23:33:12Z"
    )
    assert normalize_timestamp("2026-08-08T10:00:00.000Z") == "2026-08-08T10:00:00Z"
    assert normalize_timestamp("2026-08-08T12:00:00+02:00") == "2026-08-08T10:00:00Z"
    assert normalize_timestamp("2026-08-08T10:00:00") == "2026-08-08T10:00:00Z"
    assert normalize_timestamp(None) is None
    assert normalize_timestamp("not a date") is None


def test_filter_positions_sorts_and_drops_invalid() -> None:
    """Waypoints are returned oldest first, invalid ones removed."""
    waypoints = filter_positions(RAW_POSITIONS)

    assert [(w["lat"], w["lng"]) for w in waypoints] == [(1.0, 2.0), (3.0, 4.0)]
    assert [w["time"] for w in waypoints] == [
        "2026-08-08T10:00:00Z",
        "2026-08-08T12:00:00Z",
    ]


def test_filter_positions_without_timestamps_reverses() -> None:
    """Without timestamps the API order is reversed (newest first upstream)."""
    waypoints = filter_positions(
        [
            {"lat": 2.0, "lng": 2.0, "radius": 10},
            {"lat": 1.0, "lng": 1.0, "radius": 10},
        ]
    )

    assert [w["lat"] for w in waypoints] == [1.0, 2.0]


def test_build_geojson_track() -> None:
    """The track carries coordinates and parallel timestamps."""
    waypoints = filter_positions(RAW_POSITIONS)
    data = build_geojson_track(waypoints, "Lola")

    feature = data["features"][0]
    assert feature["geometry"]["type"] == "LineString"
    assert feature["geometry"]["coordinates"] == [[2.0, 1.0], [4.0, 3.0]]
    assert feature["properties"]["coordinateProperties"]["times"] == [
        "2026-08-08T10:00:00Z",
        "2026-08-08T12:00:00Z",
    ]
    assert feature["properties"]["name"] == "Lola Route"


def test_build_geojson_points() -> None:
    """Each waypoint becomes a point feature keeping its attributes."""
    waypoints = filter_positions(RAW_POSITIONS)
    data = build_geojson_points(waypoints, "Lola")

    assert len(data["features"]) == 2
    first = data["features"][0]
    assert first["geometry"] == {"type": "Point", "coordinates": [2.0, 1.0]}
    assert first["properties"]["time"] == "2026-08-08T10:00:00Z"
    assert first["properties"]["positionType"] == "WIFI"
    assert first["properties"]["radius"] == 10
    assert first["properties"]["sequence"] == 0


def test_build_gpx() -> None:
    """GPX contains one timestamped track point per waypoint."""
    waypoints = filter_positions(RAW_POSITIONS)
    gpx = build_gpx(waypoints, "Lola & Co")

    assert gpx.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert 'version="1.1"' in gpx
    assert gpx.count("<trkpt") == 2
    assert '<trkpt lat="1.0" lon="2.0">' in gpx
    assert "<time>2026-08-08T10:00:00Z</time>" in gpx
    assert "Lola &amp; Co Route" in gpx
    assert gpx.rstrip().endswith("</gpx>")


def test_build_gpx_without_timestamps() -> None:
    """A waypoint without a timestamp is still exported, just without time."""
    gpx = build_gpx(filter_positions([{"lat": 1.0, "lng": 2.0, "radius": 10}]), "Lola")

    assert gpx.count("<trkpt") == 1
    assert "<time>" not in gpx
