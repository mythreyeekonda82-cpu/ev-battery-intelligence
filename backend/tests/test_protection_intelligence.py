from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.protection_intelligence import (
    detect_fault_combinations,
    explain_protection_decision,
    calculate_safety_confidence,
    detect_behaviour_change,
    learn_protection_failures,
    detect_sensor_disagreement,
    predict_fault_sequence,
    analyse_battery,
)


NOW = datetime(2026, 1, 1, 12, 0, 0)


def snapshot(**overrides):

    battery = {
        "battery_id": "BAT-001",
        "voltage": 390.0,
        "current": 60.0,
        "temperature": 30.0,
        "soc": 70.0,
        "soh": 95.0,
        "cell_delta_mv": 10.0,
        "updated_at": NOW.isoformat(),
    }

    battery.update(overrides)
    battery["power_kw"] = battery["voltage"] * battery["current"] / 1000.0

    return battery


def history(count, temperature_step=0.0, voltage_step=0.0, current_step=0.0):

    start = NOW - timedelta(minutes=5 * count)

    return [
        SimpleNamespace(
            timestamp=start + timedelta(minutes=5 * i),
            temperature=30.0 + temperature_step * i,
            voltage=390.0 + voltage_step * i,
            current=60.0 + current_step * i,
        )
        for i in range(count)
    ]


def test_healthy_battery_has_no_combinations():

    result = detect_fault_combinations(snapshot(), history(12))

    assert result["detected"] is False
    assert result["severity"] == "NORMAL"


def test_hot_and_high_current_is_combination():

    battery = snapshot(temperature=42.0, current=135.0)

    result = detect_fault_combinations(battery, history(12))
    codes = [c["code"] for c in result["combinations"]]

    assert "HIGH_TEMP_HIGH_CURRENT" in codes
    assert result["severity"] == "HIGH"


def test_rising_temperature_with_falling_voltage_is_runaway_precursor():

    battery = snapshot(temperature=43.0)

    # Over one hour: +12 °C and -24 V.
    rows = history(12, temperature_step=1.0, voltage_step=-2.0)

    result = detect_fault_combinations(battery, rows)
    codes = [c["code"] for c in result["combinations"]]

    assert "THERMAL_RUNAWAY_PRECURSOR" in codes
    assert result["severity"] == "CRITICAL"


def test_decision_normal_when_healthy():

    result = explain_protection_decision(snapshot(), history(12))

    assert result["decision"] == "NORMAL_OPERATION"
    assert result["warning_generated"] is False


def test_decision_stop_charging_on_high_voltage():

    battery = snapshot(voltage=435.0, current=-40.0)

    result = explain_protection_decision(battery, history(12))

    assert result["decision"] == "STOP_CHARGING"
    assert result["primary_cause"] == "Voltage (high)"
    assert any("435.0" in step for step in result["conditions_to_recover"])


def test_decision_isolate_on_critical_temperature():

    battery = snapshot(temperature=47.0)

    result = explain_protection_decision(battery, history(12))

    assert result["decision"] == "ISOLATE_BATTERY"
    assert result["decision_path"]


def test_confidence_high_with_good_data():

    result = calculate_safety_confidence(snapshot(), history(12), now=NOW)

    assert result["confidence_level"] == "HIGH"
    assert result["safety_status"] == "SAFE"
    assert result["limitations"] == []


def test_confidence_low_with_stale_sparse_data():

    battery = snapshot(
        updated_at=(NOW - timedelta(minutes=15)).isoformat()
    )
    battery["soh"] = None

    result = calculate_safety_confidence(battery, history(1), now=NOW)

    assert result["confidence_level"] == "LOW"
    assert "soh" in result["missing_parameters"]


def test_confidence_flags_inconsistent_power():

    battery = snapshot()
    battery["power_kw"] = 99.0

    result = calculate_safety_confidence(battery, history(12), now=NOW)

    assert any("power" in item for item in result["limitations"])
    assert result["confidence_score"] < 100


def rows(values, minutes=5):
    """Telemetry rows ending at NOW from a list of field dicts."""

    start = NOW - timedelta(minutes=minutes * (len(values) - 1))

    result = []

    for i, item in enumerate(values):
        row = {
            "temperature": 30.0,
            "voltage": 390.0,
            "current": 60.0,
            "soc": 70.0,
        }
        row.update(item)
        row["power_kw"] = row["voltage"] * row["current"] / 1000.0
        row["timestamp"] = start + timedelta(minutes=minutes * i)
        result.append(SimpleNamespace(**row))

    return result


def wobble(i):
    return 0.3 if i % 2 else -0.3


def test_behaviour_unavailable_with_little_history():

    result = detect_behaviour_change(history(4))

    assert result["available"] is False


def test_behaviour_stable_battery_unchanged():

    data = rows([{"temperature": 30 + wobble(i)} for i in range(36)])

    result = detect_behaviour_change(data)

    assert result["available"] is True
    assert result["changed"] is False


def test_behaviour_detects_temperature_shift():

    # Two hours at 30 °C, then the last hour at 36 °C.
    data = rows(
        [{"temperature": 30 + wobble(i)} for i in range(24)]
        + [{"temperature": 36 + wobble(i)} for i in range(12)]
    )

    result = detect_behaviour_change(data)
    flagged = [m["metric"] for m in result["metrics"] if m["changed"]]

    assert result["changed"] is True
    assert flagged == ["Temperature"]


def test_learning_needs_enough_history():

    result = learn_protection_failures(snapshot(), history(5))

    assert result["learning_status"] == "INSUFFICIENT_DATA"


def test_learning_flags_sustained_and_recurring_breach():

    temps = (
        [30] * 10
        + [41, 43]          # precursors
        + [46, 47, 47, 46]  # 15-minute breach
        + [42] * 4
        + [46]              # returns within the hour
        + [30] * 5
    )

    data = rows([{"temperature": t} for t in temps])

    result = learn_protection_failures(snapshot(), data)
    over_temp = next(p for p in result["protections"] if p["code"] == "OVER_TEMPERATURE")

    assert result["learning_status"] == "LEARNED"
    assert over_temp["episodes"] == 2
    assert over_temp["sustained_breaches"] == 1
    assert over_temp["quick_recurrences"] == 1
    # Last readings before the two breaches were 43 and 42.
    assert over_temp["learned_early_warning"] == 42
    assert over_temp["suggest_earlier_warning"] is False
    assert len(result["failures"]) == 2


def test_learning_no_breaches_learns_ranges():

    data = rows([{"temperature": 30 + wobble(i)} for i in range(20)])

    result = learn_protection_failures(snapshot(), data)

    assert result["learning_status"] == "LEARNING"
    assert result["failures"] == []
    assert "temperature" in result["normal_ranges"]


def test_sensors_agree_when_consistent():

    data = rows([
        {
            "temperature": 30 + wobble(i),
            "voltage": 390 + wobble(i),
            "current": 60 + wobble(i),
        }
        for i in range(12)
    ])

    result = detect_sensor_disagreement(snapshot(), data, now=NOW)

    assert result["disagreement_detected"] is False


def test_sensors_detect_stuck_temperature():

    data = rows([
        {"temperature": 30.0, "voltage": 390 + i, "current": 60 + i}
        for i in range(12)
    ])

    result = detect_sensor_disagreement(snapshot(), data, now=NOW)

    assert result["disagreement_detected"] is True
    assert "temperature" in result["suspect_sensors"]


def test_sensors_idle_current_is_not_stuck():

    data = rows([
        {"temperature": 30 + wobble(i), "voltage": 390 + wobble(i), "current": 0.0}
        for i in range(12)
    ])

    battery = snapshot(current=0.0)

    result = detect_sensor_disagreement(battery, data, now=NOW)

    assert "current" not in result["suspect_sensors"]


def test_sensors_ignore_single_glitch():

    temps = [30 + wobble(i) for i in range(12)]
    temps[6] = 37.0  # one spike, e.g. after a restart

    data = rows([
        {"temperature": t, "voltage": 390 + wobble(i), "current": 60 + wobble(i)}
        for i, t in enumerate(temps)
    ])

    result = detect_sensor_disagreement(snapshot(), data, now=NOW)

    assert result["disagreement_detected"] is False


def test_sensors_flag_repeated_jumps():

    # Two separate spikes.
    temps = [30, 30, 37, 30, 30, 30, 37, 30, 30]

    data = rows([
        {"temperature": t, "voltage": 390 + wobble(i), "current": 60 + wobble(i)}
        for i, t in enumerate(temps)
    ])

    result = detect_sensor_disagreement(snapshot(), data, now=NOW)

    assert result["suspect_sensors"] == ["temperature"]


def test_sensors_detect_heating_without_load():

    data = rows([
        {"temperature": 30 + 4 * i, "current": 10.0}
        for i in range(4)
    ])

    result = detect_sensor_disagreement(snapshot(), data, now=NOW)
    failed = [c["check"] for c in result["checks"] if c["status"] == "DISAGREE"]

    assert "Temperature vs current" in failed


def test_prediction_none_when_flat():

    data = rows([{"temperature": 30 + wobble(i)} for i in range(12)])

    result = predict_fault_sequence(snapshot(), data)

    assert result["prediction_available"] is False


def test_prediction_orders_rising_temperature():

    # +6 °C per hour, currently 37 °C: warning in ~30 min,
    # critical in ~80 min.
    data = rows([{"temperature": 31.5 + 0.5 * i} for i in range(12)])

    result = predict_fault_sequence(snapshot(temperature=37.0), data)
    events = result["events"]

    assert [e["level"] for e in events] == ["WARNING", "CRITICAL"]
    assert 25 <= events[0]["eta_minutes"] <= 35
    assert events[0]["confidence"] == "HIGH"
    assert result["likely_progression"][0] == "BMS thermal derating"


def test_strategy_healthy_is_routine():

    data = rows([
        {"temperature": 30 + wobble(i), "voltage": 390 + wobble(i), "current": 60 + wobble(i)}
        for i in range(36)
    ])

    strategy = analyse_battery(snapshot(), data)["personalised_protection_strategy"]

    assert strategy["immediate_count"] == 0
    assert strategy["actions"][0]["priority"] == "PLANNED"


def test_strategy_puts_critical_actions_first():

    battery = snapshot(temperature=47.0, soh=80.0)

    strategy = analyse_battery(battery, history(12))["personalised_protection_strategy"]
    priorities = [a["priority"] for a in strategy["actions"]]

    assert strategy["immediate_count"] >= 1
    assert priorities == sorted(priorities, key=["IMMEDIATE", "SOON", "PLANNED"].index)
    assert any(a["source"] == "Battery state" for a in strategy["actions"])
