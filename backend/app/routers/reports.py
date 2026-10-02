import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, security
from ..database import get_db


router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"]
)


@router.get("/batteries.csv")
def battery_report(
    current_user=Depends(
        security.get_current_user
    ),
    db: Session = Depends(get_db)
):

    batteries = (
        db.query(models.Battery)
        .order_by(
            models.Battery.battery_id
        )
        .all()
    )

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Battery",
        "SOC %",
        "SOH %",
        "Voltage",
        "Current",
        "Temperature",
        "Cycles",
        "Range KM",
        "Status",
        "Weak Reason"
    ])

    for battery in batteries:

        writer.writerow([
            battery.battery_id,
            battery.soc,
            battery.soh,
            battery.voltage,
            battery.current,
            battery.temperature,
            battery.cycles,
            battery.range_km,
            battery.status,
            battery.weak_reason or ""
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
            "attachment; "
            "filename=EV_Battery_Report.csv"
        }
    )