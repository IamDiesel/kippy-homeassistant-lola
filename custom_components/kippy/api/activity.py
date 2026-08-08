"""API endpoint for retrieving activity statistics."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from ._base import BaseKippyApi

GET_ACTIVITIES_CAT_QUERY = """
query getActivitiesCat($petId: String!, $weekIndex: Int!, $from: Int!, $to: Int!) {
  getActivitiesCat(petId: $petId, weekIndex: $weekIndex, from: $from, to: $to) {
    activityReport {
      walk { value }
      sleep { value }
      calories { value }
      steps { value }
      feed { value }
      jumps { value }
      onTheMove { value }
      highMovement { value }
      grooming { value }
    }
  }
}
"""


class ActivityEndpoint(BaseKippyApi):
    """Mixin implementing the activity category endpoint."""

    async def get_activity_categories(
        self,
        pet_id: str,
        from_date: str,
        to_date: str,
        time_division: int,
        _weeks: int,
    ) -> Dict[str, Any]:
        """Retrieve activity categories via GraphQL."""

        # AWS erwartet exakt den Start und das Ende der aktuellen Woche in Sekunden
        dt = datetime.now()
        start_of_week = dt - timedelta(days=dt.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_of_week + timedelta(
            days=6, hours=23, minutes=59, seconds=59
        )

        from_ts = int(start_of_week.timestamp())
        to_ts = int(end_of_week.timestamp())

        year, week, _ = dt.isocalendar()
        week_index = int(f"{year}{week:02d}")

        variables = {
            "petId": str(pet_id),
            "weekIndex": week_index,
            "from": from_ts,
            "to": to_ts,
        }

        data = await self.execute_graphql(GET_ACTIVITIES_CAT_QUERY, variables)
        report = data.get("getActivitiesCat", {}).get("activityReport") or {}

        # Das Datum muss exakt `from_date` entsprechen, damit sensor.py es zuordnen kann
        daily_entry = {
            "date": from_date,
            "walk": {"value": report.get("walk", {}).get("value", 0)},
            "sleep": {"value": report.get("sleep", {}).get("value", 0)},
            "calories": {"value": report.get("calories", {}).get("value", 0)},
            "steps": {"value": report.get("steps", {}).get("value", 0)},
            "feed": {"value": report.get("feed", {}).get("value", 0)},
            "eat": {"value": report.get("feed", {}).get("value", 0)},
            "jumps": {"value": report.get("jumps", {}).get("value", 0)},
            "on_the_move": {"value": report.get("onTheMove", {}).get("value", 0)},
            "high_movement": {"value": report.get("highMovement", {}).get("value", 0)},
            "run": {"value": report.get("highMovement", {}).get("value", 0)},
            "play": {"value": report.get("highMovement", {}).get("value", 0)},
            "climb": {"value": report.get("highMovement", {}).get("value", 0)},
            "grooming": {"value": report.get("grooming", {}).get("value", 0)},
            "rest": {"value": report.get("onTheMove", {}).get("value", 0)},
            "relax": {"value": report.get("onTheMove", {}).get("value", 0)},
        }

        return {"activities": [daily_entry], "avg": {}, "health": {}}
