"""API endpoint for retrieving pets and their associated Kippy devices."""

from __future__ import annotations

from typing import Any

from ._base import BaseKippyApi

GET_PETS_QUERY = """
query getPets {
  getPets {
    pets {
      id
      name
      species
      image {
        url
      }
    }
  }
}
"""

GET_PRODUCTS_QUERY = """
query getProducts($petId: String!) {
  getProducts(petId: $petId) {
    products {
      id
      entityType
      serialNumber
      deviceType
      subscriptionIsActive
      lastKnownStatus {
        energySavingMode
        firmwareVersion
      }
    }
  }
}
"""

GET_PETLINK_GPS_QUERY = """
query getPetlinkGps($id: String!) {
  getPetlinkGps(id: $id) {
    petlinkGps {
      settings {
        updateFrequency
        enableGpsOnDefault
      }
    }
  }
}
"""


class PetsEndpoint(BaseKippyApi):
    """Mixin implementing the pets endpoint."""

    async def get_pet_kippy_list(self) -> list[dict[str, Any]]:
        """Retrieve a list of all pets and their associated Kippy devices."""

        pets_data = await self.execute_graphql(GET_PETS_QUERY)
        # Sicheres Entpacken, falls die Antwort null ist
        pets_resp = pets_data.get("getPets") or {}
        pets = pets_resp.get("pets") or []

        combined_list = []

        for pet in pets:
            pet_id = pet.get("id")
            if not pet_id:
                continue

            products_data = await self.execute_graphql(
                GET_PRODUCTS_QUERY, {"petId": str(pet_id)}
            )
            products_resp = products_data.get("getProducts") or {}
            products = products_resp.get("products") or []

            for product in products:
                if product.get("entityType") in (
                    "PETLINK_GPS",
                    "KIPPY_GPS",
                    "EVO_GPS",
                    "TRACKER",
                ):
                    product_id = product.get("id")

                    # Zusätzliche Abfrage für die gerätespezifischen Einstellungen
                    settings = {}
                    if product_id:
                        gps_data = await self.execute_graphql(
                            GET_PETLINK_GPS_QUERY, {"id": str(product_id)}
                        )
                        gps_resp = gps_data.get("getPetlinkGps") or {}
                        petlink_gps = gps_resp.get("petlinkGps") or {}
                        settings = petlink_gps.get("settings") or {}

                    # Mapping der Spezies auf die numerischen Legacy-Werte
                    species = pet.get("species", "")
                    pet_kind = (
                        "3" if species == "CAT" else "4" if species == "DOG" else "1"
                    )

                    # Profilbild extrahieren
                    image_url = None
                    image_data = pet.get("image")
                    if isinstance(image_data, dict):
                        image_url = image_data.get("url")

                    status = product.get("lastKnownStatus") or {}

                    # Abo-Status simulieren
                    is_active = product.get("subscriptionIsActive")
                    expired_days = -1 if is_active else 1

                    esm = status.get("energySavingMode")
                    energy_saving_mode = 1 if esm == "ON" else 0
                    gps_on_default = 1 if settings.get("enableGpsOnDefault") else 0

                    # Das flache Legacy-Dictionary für den Coordinator
                    combined_list.append(
                        {
                            "petID": pet_id,
                            "petName": pet.get("name"),
                            "petKind": pet_kind,
                            "imageCloudURL": image_url,
                            "kippyID": product_id,
                            "kippy_id": product_id,
                            "kippySerial": product.get("serialNumber"),
                            "kippyIMEI": product.get("serialNumber"),  # Fallback
                            "kippyType": product.get("deviceType"),
                            "kippyFirmware": status.get("firmwareVersion"),
                            "updateFrequency": settings.get("updateFrequency", 1),
                            "gpsOnDefault": gps_on_default,
                            "gps_on_default": gps_on_default,
                            "energySavingMode": energy_saving_mode,
                            "energySavingModePending": False,
                            "expired_days": expired_days,
                            "firmware_need_upgrade": False,
                        }
                    )

        return combined_list
