"""
EV Charging Station Service

Provides demonstration charging station data and
calculates distances from a vehicle location.
"""

from math import radians, sin, cos, sqrt, atan2


STATIONS = [
    {
        "id": "ST001",
        "name": "EV Fast Charge - Central",
        "latitude": 16.9891,
        "longitude": 82.2475,
        "charger_type": "DC Fast",
        "power_kw": 60,
        "connectors": 2,
        "available": True,
    },
    {
        "id": "ST002",
        "name": "GreenCharge Station",
        "latitude": 16.9750,
        "longitude": 82.2300,
        "charger_type": "DC Fast",
        "power_kw": 120,
        "connectors": 4,
        "available": True,
    },
    {
        "id": "ST003",
        "name": "EV Hub",
        "latitude": 17.0005,
        "longitude": 82.2700,
        "charger_type": "AC",
        "power_kw": 22,
        "connectors": 3,
        "available": False,
    },
    {
        "id": "ST004",
        "name": "Rapid EV Point",
        "latitude": 16.9600,
        "longitude": 82.2150,
        "charger_type": "DC Fast",
        "power_kw": 80,
        "connectors": 2,
        "available": True,
    },
]


def calculate_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:

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
    limit: int = 5,
):
    results = []

    for station in STATIONS:

        distance = calculate_distance_km(
            latitude,
            longitude,
            station["latitude"],
            station["longitude"],
        )

        station_copy = station.copy()

        station_copy["distance_km"] = round(
            distance,
            2,
        )

        results.append(station_copy)

    results.sort(
        key=lambda x: x["distance_km"]
    )

    return results[:limit]