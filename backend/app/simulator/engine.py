import random
from datetime import datetime


# ============================================================
# BATTERY SIMULATION CONSTANTS
# ============================================================

TOTAL_VEHICLES = 56

MIN_SOC = 10.0
MAX_SOC = 98.0

MIN_SOH = 55.0
MAX_SOH = 100.0

MIN_CURRENT = 20.0
MAX_CURRENT = 145.0

MIN_TEMPERATURE = 20.0
MAX_TEMPERATURE = 52.0


# ============================================================
# VEHICLE CONFIGURATION
# ============================================================

def create_vehicle_config(vehicle_number: int):
    """
    Create realistic configuration for one EV.

    Vehicle numbers 1-56 are generated automatically.
    """

    vehicle_id = f"EV-{vehicle_number:03d}"
    battery_id = f"BAT-{vehicle_number:03d}"

    # Give every vehicle slightly different characteristics.
    base_voltage = random.uniform(375.0, 405.0)
    capacity_kwh = random.uniform(62.0, 82.0)
    base_temperature = random.uniform(27.0, 35.0)
    nominal_current = random.uniform(55.0, 100.0)

    # Most vehicles are healthy.
    initial_soh = random.uniform(88.0, 99.0)

    # Intentionally create several different conditions
    # so the dashboard has meaningful fleet intelligence.
    if vehicle_number in [3, 17, 28, 41, 52]:
        initial_soh = random.uniform(68.0, 82.0)

    if vehicle_number in [9, 34, 47]:
        initial_soh = random.uniform(82.0, 88.0)

    return {
        "vehicle_id": vehicle_id,
        "battery_id": battery_id,
        "name": f"Vehicle {vehicle_number:02d}",
        "model": f"EV Model {(vehicle_number % 5) + 1}",

        "base_voltage": base_voltage,
        "capacity_kwh": capacity_kwh,
        "base_temperature": base_temperature,
        "nominal_current": nominal_current,

        "initial_soh": initial_soh,
    }


# ============================================================
# BATTERY SIMULATION ENGINE
# ============================================================

class BatterySimulationEngine:

    def __init__(self):
        self.batteries = {}

        for vehicle_number in range(
            1,
            TOTAL_VEHICLES + 1,
        ):
            config = create_vehicle_config(
                vehicle_number
            )

            battery_id = config["battery_id"]

            self.batteries[battery_id] = {
                **config,

                "soc": random.uniform(
                    55.0,
                    95.0,
                ),

                "soh": config["initial_soh"],

                "voltage": config["base_voltage"],

                "current": config["nominal_current"],

                "temperature": config["base_temperature"],

                "cell_delta_mv": (
                    random.uniform(5.0, 18.0)
                ),

                "cycle_count": random.randint(
                    100,
                    850,
                ),

                "updated_at": datetime.utcnow(),
            }


    # ========================================================
    # UTILITY
    # ========================================================

    @staticmethod
    def clamp(
        value,
        minimum,
        maximum,
    ):
        return max(
            minimum,
            min(value, maximum),
        )


    # ========================================================
    # UPDATE ONE BATTERY
    # ========================================================

    def _update_battery(
        self,
        battery_id: str,
    ):

        battery = self.batteries[battery_id]

        # ----------------------------------------------------
        # SOC
        # ----------------------------------------------------

        soc_change = random.uniform(
            -0.35,
            0.18,
        )

        battery["soc"] = self.clamp(
            battery["soc"] + soc_change,
            MIN_SOC,
            MAX_SOC,
        )


        # ----------------------------------------------------
        # CURRENT
        # ----------------------------------------------------

        current_change = random.uniform(
            -7.0,
            7.0,
        )

        battery["current"] = self.clamp(
            battery["current"] + current_change,
            MIN_CURRENT,
            MAX_CURRENT,
        )


        # ----------------------------------------------------
        # VOLTAGE
        # ----------------------------------------------------

        target_voltage = (
            battery["base_voltage"]
            + (
                battery["soc"] - 50.0
            ) * 0.20
        )

        voltage_noise = random.uniform(
            -2.0,
            2.0,
        )

        battery["voltage"] = (
            battery["voltage"] * 0.80
            + (
                target_voltage
                + voltage_noise
            ) * 0.20
        )


        # ----------------------------------------------------
        # TEMPERATURE
        # ----------------------------------------------------

        heat_from_current = max(
            0.0,
            battery["current"] - 45.0,
        ) * 0.045

        target_temperature = (
            battery["base_temperature"]
            + heat_from_current
        )

        temperature_noise = random.uniform(
            -0.7,
            0.7,
        )

        battery["temperature"] = (
            battery["temperature"] * 0.82
            + (
                target_temperature
                + temperature_noise
            ) * 0.18
        )

        battery["temperature"] = self.clamp(
            battery["temperature"],
            MIN_TEMPERATURE,
            MAX_TEMPERATURE,
        )


        # ----------------------------------------------------
        # CELL IMBALANCE
        # ----------------------------------------------------

        # Vehicles with degraded batteries have
        # significantly higher cell imbalance.

        vehicle_number = int(
            battery["vehicle_id"].split("-")[1]
        )

        if vehicle_number in [
            3,
            17,
            28,
            41,
            52,
        ]:

            target_delta = random.uniform(
                30.0,
                58.0,
            )

        elif vehicle_number in [
            9,
            34,
            47,
        ]:

            target_delta = random.uniform(
                22.0,
                34.0,
            )

        else:

            target_delta = random.uniform(
                5.0,
                18.0,
            )

        battery["cell_delta_mv"] = (
            battery["cell_delta_mv"] * 0.82
            + target_delta * 0.18
        )


        # ----------------------------------------------------
        # SOH DEGRADATION
        # ----------------------------------------------------

        degradation = random.uniform(
            0.000,
            0.004,
        )

        if vehicle_number in [
            3,
            17,
            28,
            41,
            52,
        ]:

            degradation += random.uniform(
                0.002,
                0.009,
            )

        battery["soh"] = self.clamp(
            battery["soh"] - degradation,
            MIN_SOH,
            MAX_SOH,
        )


        # ----------------------------------------------------
        # BATTERY CYCLES
        # ----------------------------------------------------

        if random.random() < 0.01:
            battery["cycle_count"] += 1


        battery["updated_at"] = (
            datetime.utcnow()
        )


    # ========================================================
    # GET ONE BATTERY
    # ========================================================

    def get_battery(
        self,
        battery_id: str,
    ):

        battery_id = battery_id.upper()

        if battery_id not in self.batteries:
            return None

        self._update_battery(
            battery_id
        )

        battery = self.batteries[
            battery_id
        ]

        capacity_kwh = (
            battery["capacity_kwh"]
        )

        remaining_kwh = (
            capacity_kwh
            * battery["soc"]
            / 100.0
            * battery["soh"]
            / 100.0
        )

        power_kw = (
            battery["voltage"]
            * battery["current"]
            / 1000.0
        )

        # Approximate 96-series-cell battery.
        min_cell_voltage = (
            battery["voltage"]
            / 96.0
        )

        max_cell_voltage = (
            min_cell_voltage
            + battery["cell_delta_mv"]
            / 1000.0
        )


        # ----------------------------------------------------
        # HEALTH STATUS
        # ----------------------------------------------------

        if (
            battery["soh"] < 70.0
            or battery["temperature"] >= 45.0
            or battery["cell_delta_mv"] >= 40.0
        ):

            health_status = "CRITICAL"

        elif (
            battery["soh"] < 85.0
            or battery["temperature"] >= 40.0
            or battery["cell_delta_mv"] >= 25.0
        ):

            health_status = "WARNING"

        else:

            health_status = "HEALTHY"


        return {

            # Vehicle information
            "vehicle_id": battery["vehicle_id"],
            "vehicle_name": battery["name"],
            "model": battery["model"],

            # Battery information
            "battery_id": battery_id,
            "battery_name": (
                f"Battery Pack "
                f"{battery_id.replace('BAT-', '')}"
            ),

            # Electrical telemetry
            "voltage": round(
                battery["voltage"],
                2,
            ),

            "current": round(
                battery["current"],
                2,
            ),

            "power_kw": round(
                power_kw,
                2,
            ),

            # Battery state
            "soc": round(
                battery["soc"],
                2,
            ),

            "soh": round(
                battery["soh"],
                2,
            ),

            "temperature": round(
                battery["temperature"],
                2,
            ),

            # Capacity
            "capacity_kwh": round(
                capacity_kwh,
                2,
            ),

            "remaining_kwh": round(
                remaining_kwh,
                2,
            ),

            # Cell information
            "cell_delta_mv": round(
                battery["cell_delta_mv"],
                2,
            ),

            "min_cell_voltage": round(
                min_cell_voltage,
                4,
            ),

            "max_cell_voltage": round(
                max_cell_voltage,
                4,
            ),

            "cell_count": 96,

            # Lifecycle
            "cycle_count": (
                battery["cycle_count"]
            ),

            # Intelligence
            "health_status": health_status,

            # Timestamp
            "updated_at": (
                battery["updated_at"]
                .isoformat()
            ),
        }


    # ========================================================
    # GET ALL BATTERIES
    # ========================================================

    def get_all_batteries(self):

        return [
            self.get_battery(
                battery_id
            )

            for battery_id
            in self.batteries
        ]


    # ========================================================
    # GET ALL VEHICLES
    # ========================================================

    def get_all_vehicles(self):

        batteries = (
            self.get_all_batteries()
        )

        vehicles = []

        for battery in batteries:

            vehicles.append(
                {
                    "vehicle_id": (
                        battery["vehicle_id"]
                    ),

                    "vehicle_name": (
                        battery["vehicle_name"]
                    ),

                    "model": (
                        battery["model"]
                    ),

                    "battery_id": (
                        battery["battery_id"]
                    ),

                    "soc": (
                        battery["soc"]
                    ),

                    "soh": (
                        battery["soh"]
                    ),

                    "temperature": (
                        battery["temperature"]
                    ),

                    "voltage": (
                        battery["voltage"]
                    ),

                    "current": (
                        battery["current"]
                    ),

                    "power_kw": (
                        battery["power_kw"]
                    ),

                    "cell_delta_mv": (
                        battery["cell_delta_mv"]
                    ),

                    "health_status": (
                        battery["health_status"]
                    ),

                    "cycle_count": (
                        battery["cycle_count"]
                    ),

                    "updated_at": (
                        battery["updated_at"]
                    ),
                }
            )

        return vehicles


    # ========================================================
    # FLEET SUMMARY
    # ========================================================

    def get_summary(self):

        batteries = (
            self.get_all_batteries()
        )

        if not batteries:

            return {
                "total_vehicles": 0,
                "healthy": 0,
                "warning": 0,
                "critical": 0,
                "average_soc": 0,
                "average_soh": 0,
                "average_temperature": 0,
                "total_power_kw": 0,
                "weakest_vehicle": None,
            }


        healthy = 0
        warning = 0
        critical = 0

        for battery in batteries:

            status = (
                battery["health_status"]
            )

            if status == "HEALTHY":
                healthy += 1

            elif status == "WARNING":
                warning += 1

            else:
                critical += 1


        weakest = min(
            batteries,
            key=lambda battery: (
                battery["soh"]
            ),
        )


        return {

            "total_vehicles": len(
                batteries
            ),

            "healthy": healthy,

            "warning": warning,

            "critical": critical,

            "average_soc": round(
                sum(
                    battery["soc"]
                    for battery in batteries
                )
                / len(batteries),
                2,
            ),

            "average_soh": round(
                sum(
                    battery["soh"]
                    for battery in batteries
                )
                / len(batteries),
                2,
            ),

            "average_temperature": round(
                sum(
                    battery["temperature"]
                    for battery in batteries
                )
                / len(batteries),
                2,
            ),

            "total_power_kw": round(
                sum(
                    battery["power_kw"]
                    for battery in batteries
                ),
                2,
            ),

            "weakest_vehicle": {

                "vehicle_id": (
                    weakest["vehicle_id"]
                ),

                "vehicle_name": (
                    weakest["vehicle_name"]
                ),

                "battery_id": (
                    weakest["battery_id"]
                ),

                "soh": (
                    weakest["soh"]
                ),

                "soc": (
                    weakest["soc"]
                ),

                "temperature": (
                    weakest["temperature"]
                ),

                "cell_delta_mv": (
                    weakest["cell_delta_mv"]
                ),

                "health_status": (
                    weakest["health_status"]
                ),
            },
        }


# ============================================================
# GLOBAL SIMULATION ENGINE
# ============================================================

simulation_engine = (
    BatterySimulationEngine()
)


def get_simulation_engine():

    return simulation_engine