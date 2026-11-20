from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services.protection_alerts import record_protection_alerts


NOW = datetime(2026, 1, 1, 12, 0, 0)


def session():

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)

    return sessionmaker(bind=engine)()


def battery(**overrides):

    data = {
        "battery_id": "BAT-001",
        "voltage": 390.0,
        "current": 60.0,
        "temperature": 30.0,
        "soc": 70.0,
        "soh": 95.0,
        "cell_delta_mv": 10.0,
        "updated_at": NOW.isoformat(),
    }

    data.update(overrides)
    data["power_kw"] = data["voltage"] * data["current"] / 1000.0

    return data


def test_healthy_battery_raises_no_alerts():

    db = session()

    assert record_protection_alerts(db, battery(), [], now=NOW) == 0


def test_critical_temperature_raises_alert_once():

    db = session()
    hot = battery(temperature=47.0)

    first = record_protection_alerts(db, hot, [], now=NOW)
    db.commit()

    again = record_protection_alerts(db, hot, [], now=NOW + timedelta(minutes=5))
    db.commit()

    alerts = db.query(models.Alert).all()

    assert first >= 1
    assert again == 0
    assert any(a.alert_type == "PROTECTION_ISOLATE_BATTERY" for a in alerts)
    assert all(a.battery_id == "BAT-001" for a in alerts)


def test_alert_repeats_after_acknowledged():

    db = session()
    hot = battery(temperature=47.0)

    record_protection_alerts(db, hot, [], now=NOW)
    db.commit()

    for alert in db.query(models.Alert).all():
        alert.is_read = True
    db.commit()

    again = record_protection_alerts(db, hot, [], now=NOW + timedelta(minutes=5))

    assert again >= 1
