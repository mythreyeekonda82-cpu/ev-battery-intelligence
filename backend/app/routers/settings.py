from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from .. import models, security
from ..database import get_db


router = APIRouter(
    prefix="/api/settings",
    tags=["Settings"]
)


# Settings update request model
class SettingsUpdate(BaseModel):
    temperature_warning: float = Field(default=40.0, ge=0, le=100)
    temperature_critical: float = Field(default=45.0, ge=0, le=120)
    soc_warning: float = Field(default=20.0, ge=0, le=100)
    soh_warning: float = Field(default=70.0, ge=0, le=100)
    email_enabled: bool = False
    whatsapp_enabled: bool = False
    weekly_reports: bool = False


def get_or_create_settings(user, db: Session):

    settings = (
        db.query(models.UserSettings)
        .filter(
            models.UserSettings.user_id == user.id
        )
        .first()
    )

    if not settings:
        settings = models.UserSettings(
            user_id=user.id,
            temperature_warning=40.0,
            temperature_critical=45.0,
            soc_warning=20.0,
            soh_warning=70.0,
            email_enabled=False,
            whatsapp_enabled=False,
            weekly_reports=False
        )

        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


@router.get("")
def get_settings(
    current_user=Depends(security.get_current_user),
    db: Session = Depends(get_db)
):

    settings = get_or_create_settings(
        current_user,
        db
    )

    return {
        "temperature_warning": settings.temperature_warning,
        "temperature_critical": settings.temperature_critical,
        "soc_warning": settings.soc_warning,
        "soh_warning": settings.soh_warning,
        "email_enabled": settings.email_enabled,
        "whatsapp_enabled": settings.whatsapp_enabled,
        "weekly_reports": settings.weekly_reports
    }


@router.put("")
def update_settings(
    payload: SettingsUpdate,
    current_user=Depends(security.get_current_user),
    db: Session = Depends(get_db)
):

    settings = get_or_create_settings(
        current_user,
        db
    )

    settings.temperature_warning = payload.temperature_warning
    settings.temperature_critical = payload.temperature_critical
    settings.soc_warning = payload.soc_warning
    settings.soh_warning = payload.soh_warning
    settings.email_enabled = payload.email_enabled
    settings.whatsapp_enabled = payload.whatsapp_enabled
    settings.weekly_reports = payload.weekly_reports

    db.commit()
    db.refresh(settings)

    return {
        "success": True,
        "message": "Settings saved successfully."
    }