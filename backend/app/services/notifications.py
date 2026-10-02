import os
import smtplib

from email.message import EmailMessage

import httpx


def send_email(
    recipient: str,
    subject: str,
    message: str
):

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(
        os.getenv("SMTP_PORT", "587")
    )
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv(
        "SMTP_PASSWORD"
    )

    if not all([
        smtp_host,
        smtp_user,
        smtp_password
    ]):

        return {
            "success": False,
            "message": (
                "SMTP is not configured yet."
            )
        }

    email = EmailMessage()

    email["Subject"] = subject
    email["From"] = smtp_user
    email["To"] = recipient

    email.set_content(message)

    try:

        with smtplib.SMTP(
            smtp_host,
            smtp_port
        ) as server:

            server.starttls()

            server.login(
                smtp_user,
                smtp_password
            )

            server.send_message(email)

        return {
            "success": True,
            "message": "Email sent successfully."
        }

    except Exception as error:

        return {
            "success": False,
            "message": str(error)
        }


async def send_whatsapp(
    phone_number: str,
    message: str
):

    token = os.getenv(
        "WHATSAPP_ACCESS_TOKEN"
    )

    phone_id = os.getenv(
        "WHATSAPP_PHONE_NUMBER_ID"
    )

    api_version = os.getenv(
        "WHATSAPP_API_VERSION",
        "v20.0"
    )

    if not token or not phone_id:

        return {
            "success": False,
            "message": (
                "WhatsApp Cloud API "
                "is not configured yet."
            )
        }

    url = (
        f"https://graph.facebook.com/"
        f"{api_version}/"
        f"{phone_id}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {
            "body": message
        }
    }

    headers = {
        "Authorization":
            f"Bearer {token}",
        "Content-Type":
            "application/json"
    }

    try:

        async with httpx.AsyncClient(
            timeout=20
        ) as client:

            response = await client.post(
                url,
                json=payload,
                headers=headers
            )

        if response.status_code >= 400:

            return {
                "success": False,
                "message": response.text
            }

        return {
            "success": True,
            "message": "WhatsApp message sent."
        }

    except Exception as error:

        return {
            "success": False,
            "message": str(error)
        }