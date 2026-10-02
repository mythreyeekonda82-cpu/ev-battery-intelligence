from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db


router = APIRouter(
    prefix="/api/settings",
    tags=["Settings"]
)


def get_or_create_settings(
    user,
    db
):

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
            email_address=user.email
        )

        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


@router.get("")
def get_settings(
    current_user=Depends(
        security.get_current_user
    ),
    db: Session = Depends(get_db)
):

    settings = get_or_create_settings(
        current_user,
        db
    )

    return {
        "temperature_warning":
            settings.temperature_warning,

        "temperature_critical":
            settings.temperature_critical,

        "minimum_soh":
            settings.minimum_soh,

        "maximum_current":
            settings.maximum_current,

        "email_enabled":
            settings.email_enabled,

        "whatsapp_enabled":
            settings.whatsapp_enabled,

        "email_address":
            settings.email_address,

        "whatsapp_number":
            settings.whatsapp_number
    }


@router.put("")
def update_settings(
    payload: schemas.SettingsUpdate,
    current_user=Depends(
        security.get_current_user
    ),
    db: Session = Depends(get_db)
):

    settings = get_or_create_settings(
        current_user,
        db
    )

    settings.temperature_warning = (
        payload.temperature_warning
    )

    settings.temperature_critical = (
        payload.temperature_critical
    )

    settings.minimum_soh = (
        payload.minimum_soh
    )

    settings.maximum_current = (
        payload.maximum_current
    )

    settings.email_enabled = (
        payload.email_enabled
    )

    settings.whatsapp_enabled = (
        payload.whatsapp_enabled
    )

    settings.email_address = (
        payload.email_address
        or current_user.email
    )

    settings.whatsapp_number = (
        payload.whatsapp_number
    )

    db.commit()

    return {
        "success": True,
        "message": "Settings saved successfully."
    }