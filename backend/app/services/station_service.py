"""
VoltIQ Open Charge Map Integration

Retrieves charging station listings from Open Charge Map
and calculates distances from the user's GPS location.
"""

import os
import json
import urllib.parse
import urllib.request

from math import radians, sin, cos, sqrt, atan2


OCM_API_URL = "https://api.openchargemap.io/v3/poi/"


def calculate_distance_km(lat1, lon1, lat2, lon2):

    earth_radius = 6371.0

    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)

    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(d_lon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius * c


def get_nearest_stations(
    latitude: float,
    longitude: float,
    limit: int = 5
):
    """
    Retrieve nearby charging stations from Open Charge Map.
    """

    api_key = os.getenv("OCM_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Open Charge Map API key is missing. "
            "Add OCM_API_KEY to backend/.env."
        )

    params = {
        "output": "json",
        "latitude": latitude,
        "longitude": longitude,
        "distance": 50,
        "distanceunit": "KM",
        "maxresults": limit,
        "compact": "true",
        "verbose": "false"
    }

    url = OCM_API_URL + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "X-API-Key": api_key,
            "User-Agent": "VoltIQ-EV-Battery-Intelligence/1.0",
            "Accept": "application/json"
        }
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=20
        ) as response:

            raw_data = response.read().decode("utf-8")

            stations_data = json.loads(raw_data)

    except Exception as exc:

        raise RuntimeError(
            f"Open Charge Map request failed: {exc}"
        )

    results = []

    for item in stations_data:

        address = item.get("AddressInfo") or {}

        station_lat = address.get("Latitude")
        station_lon = address.get("Longitude")

        if station_lat is None or station_lon is None:
            continue

        distance = calculate_distance_km(
            latitude,
            longitude,
            float(station_lat),
            float(station_lon)
        )

        connections = item.get("Connections") or []

        charger_types = []
        power_values = []

        for connection in connections:

            connection_type = (
                connection.get("ConnectionType") or {}
            )

            title = connection_type.get("Title")

            if title:
                charger_types.append(title)

            power = connection.get("PowerKW")

            if power is not None:
                power_values.append(float(power))

        status_type = item.get("StatusType") or {}

        status = status_type.get("Title") or "Status unknown"

        results.append({

            "id": item.get("ID"),

            "name": (
                address.get("Title")
                or "EV Charging Station"
            ),

            "latitude": float(station_lat),

            "longitude": float(station_lon),

            "distance_km": round(distance, 2),

            "charger_type": (
                ", ".join(sorted(set(charger_types)))
                if charger_types
                else "EV Charger"
            ),

            "power_kw": (
                max(power_values)
                if power_values
                else None
            ),

            "connectors": len(connections),

            "operational_status": status,

            "address": address.get("AddressLine1") or "",

            "town": address.get("Town") or "",

            "postcode": address.get("Postcode") or ""

        })

    results.sort(
        key=lambda station: station["distance_km"]
    )

    return results[:limit]
