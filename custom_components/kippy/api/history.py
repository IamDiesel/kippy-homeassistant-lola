from typing import Any, Dict, List

from ._base import BaseKippyApi

GET_POSITIONS_HISTORY_QUERY = """
query getPositionsHistory($petId: String!, $from: String, $to: String) {
  getPositionsHistory(petId: $petId, from: $from, to: $to) {
    positions {
      lat
      lng
      radius
      precision
      positionType
      date
      isSkip
    }
  }
}
"""


class HistoryEndpoint(BaseKippyApi):
    """Mixin für den Abruf der GPS-Historie."""

    async def get_positions_history(
        self, pet_id: str, from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """Ruft die GPS-Punkte für einen bestimmten Zeitraum ab."""

        variables = {
            "petId": str(pet_id),
            "from": from_date,  # Format: "2026-08-08T00:00:00.000Z"
            "to": to_date,
        }

        data = await self.execute_graphql(GET_POSITIONS_HISTORY_QUERY, variables)
        history = data.get("getPositionsHistory", {})

        return history.get("positions", [])
