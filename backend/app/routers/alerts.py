from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, security
from ..database import get_db


router = APIRouter(
    prefix="/api/alerts",
    tags=["Alerts"]
)


@router.get("")
def get_alerts(
    current_user=Depends(
        security.get_current_user
    ),
    db: Session = Depends(get_db)
):

    alerts = (
        db.query(models.Alert)
        .order_by(
            models.Alert.created_at.desc()
        )
        .limit(100)
        .all()
    )

    return [
        {
            "id": alert.id,
            "battery_id": alert.battery_id,
            "type": alert.alert_type,
            "severity": alert.severity,
            "message": alert.message,
            "acknowledged": alert.acknowledged,
            "created_at": (
                alert.created_at.isoformat()
            )
        }
        for alert in alerts
    ]


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    current_user=Depends(
        security.get_current_user
    ),
    db: Session = Depends(get_db)
):

    alert = (
        db.query(models.Alert)
        .filter(
            models.Alert.id == alert_id
        )
        .first()
    )

    if not alert:

        raise HTTPException(
            status_code=404,
            detail="Alert not found."
        )

    alert.acknowledged = True

    db.commit()

    return {
        "success": True,
        "message": "Alert acknowledged."
    }


@router.delete("")
def clear_alerts(
    current_user=Depends(
        security.get_current_user
    ),
    db: Session = Depends(get_db)
):

    db.query(models.Alert).delete()

    db.commit()

    return {
        "success": True,
        "message": "Alerts cleared."
    }