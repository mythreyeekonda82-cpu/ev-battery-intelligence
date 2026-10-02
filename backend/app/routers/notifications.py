from typing import Optional

from fastapi import APIRouter, HTTPException

from ..schemas import NotificationRequest


router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"]
)


@router.get("/test")
def notification_test():
    return {
        "success": True,
        "message": "Notification router is working."
    }


@router.post("/send")
def send_notification(data: NotificationRequest):
    """
    Demo notification endpoint.

    Email and WhatsApp providers will be connected
    after the backend is running correctly.
    """

    if not data.email and not data.whatsapp:
        raise HTTPException(
            status_code=400,
            detail="Provide an email address or WhatsApp number."
        )

    return {
        "success": True,
        "message": "Notification request received.",
        "email": data.email,
        "whatsapp": data.whatsapp,
        "notification": data.message
    }


@router.post("/email")
def send_email(
    message: str,
    email: Optional[str] = None
):
    """
    Email endpoint.

    This currently validates and accepts the request.
    SMTP/provider integration will be added separately.
    """

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email address is required."
        )

    return {
        "success": True,
        "channel": "email",
        "recipient": email,
        "message": message,
        "status": "queued"
    }


@router.post("/whatsapp")
def send_whatsapp(
    message: str,
    whatsapp: Optional[str] = None
):
    """
    WhatsApp endpoint.

    Actual WhatsApp Business API credentials are required
    before messages can be sent automatically.
    """

    if not whatsapp:
        raise HTTPException(
            status_code=400,
            detail="WhatsApp number is required."
        )

    return {
        "success": True,
        "channel": "whatsapp",
        "recipient": whatsapp,
        "message": message,
        "status": "queued"
    }