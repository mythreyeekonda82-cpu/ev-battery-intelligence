import random


def get_simulated_vehicle():

    # Simulated EV telemetry
    soc = random.uniform(45, 90)

    soh = random.uniform(91, 98)

    speed = random.uniform(0, 80)

    battery_capacity = 60

    range_km = 420

    charging = random.choice([
        True,
        False
    ])

    charging_power = (
        random.uniform(20, 80)
        if charging
        else 0
    )

    return {
        "vehicle_name": "EV-X1",
        "model": "EV Battery Intelligence Demo",

        "soc": round(soc, 1),

        "soh": round(soh, 1),

        "battery_capacity": battery_capacity,

        "range_km": range_km,

        "speed_kmh": round(
            speed,
            1
        ),

        "charging": charging,

        "charging_power_kw": round(
            charging_power,
            1
        ),

        # Demo GPS location
        "latitude": 16.9891,
        "longitude": 82.2475
    }