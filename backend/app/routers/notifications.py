import os

import httpx
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
async def send_notification(data: NotificationRequest):
    """
    Send a notification through the requested channel.
    """

    if not data.email and not data.whatsapp:
        raise HTTPException(
            status_code=400,
            detail="Provide an email address or WhatsApp number."
        )

    results = {}

    if data.whatsapp:
        results["whatsapp"] = await send_whatsapp_message(
            whatsapp=data.whatsapp,
            message=data.message
        )

    if data.email:
        results["email"] = {
            "status": "queued",
            "message": "Email provider integration will be added separately."
        }

    return {
        "success": True,
        "results": results
    }


@router.post("/email")
def send_email(
    message: str,
    email: str | None = None
):
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
async def send_whatsapp(
    message: str,
    whatsapp: str | None = None
):
    if not whatsapp:
        raise HTTPException(
            status_code=400,
            detail="WhatsApp number is required."
        )

    return await send_whatsapp_message(
        whatsapp=whatsapp,
        message=message
    )


async def send_whatsapp_message(
    whatsapp: str,
    message: str
):
    """
    Send a WhatsApp message through Meta WhatsApp Cloud API.

    The actual API credentials are read from environment variables.
    """

    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    api_version = os.getenv(
        "WHATSAPP_API_VERSION",
        "v20.0"
    )

    if not access_token or not phone_number_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "WhatsApp Cloud API is not configured yet. "
                "Add WHATSAPP_ACCESS_TOKEN and "
                "WHATSAPP_PHONE_NUMBER_ID."
            )
        )

    url = (
        f"https://graph.facebook.com/"
        f"{api_version}/"
        f"{phone_number_id}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": whatsapp,
        "type": "text",
        "text": {
            "body": message
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "WhatsApp Cloud API rejected the message.",
                    "provider_status": response.status_code,
                    "provider_response": response.json()
                }
            )

        return {
            "success": True,
            "channel": "whatsapp",
            "recipient": whatsapp,
            "status": "sent",
            "provider_response": response.json()
        }

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach WhatsApp Cloud API: {exc}"
        )