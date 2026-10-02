from fastapi.testclient import TestClient

from app.services import battery as B
from app.simulator.engine import Simulator
from app.main import app


def test_health_classes():

    assert (
        B.classify_health(
            3.9,
            30,
            20,
            92
        )
        == "GOOD"
    )


    assert (
        B.classify_health(
            3.9,
            41,
            20,
            92
        )
        == "WARNING"
    )


    assert (
        B.classify_health(
            3.9,
            47,
            20,
            92
        )
        == "CRITICAL"
    )


def test_runtime():

    assert (
        B.runtime_hours(
            100,
            -50
        )
        == 2.0
    )


    assert (
        B.runtime_hours(
            100,
            20
        )
        is None
    )


def test_protection():

    assert (
        B.protection_events(
            4.25,
            30,
            0
        )[0]["fault"]
        == "OVER_VOLTAGE"
    )


    assert (
        B.protection_events(
            3.9,
            30,
            0,
            online=False
        )[0]["fault"]
        == "CONNECTIVITY_LOST"
    )


def test_soc_direction():

    simulator = Simulator()

    simulator.set_mode(
        "CHARGING"
    )

    simulator.soc = 50


    for _ in range(60):

        simulator.step()


    assert simulator.soc > 50


    simulator.set_mode(
        "DRIVING"
    )

    before = simulator.soc


    for _ in range(60):

        simulator.step()


    assert simulator.soc < before


def test_api():

    client = TestClient(app)


    response = client.get(
        "/api/vehicles"
    )

    assert len(
        response.json()
    ) == 3


    response = client.post(
        "/api/simulator/EV-001/mode/CHARGING"
    )

    assert (
        response.json()["mode"]
        == "CHARGING"
    )


    response = client.get(
        "/api/battery/nope"
    )

    assert (
        response.status_code
        == 404
    )