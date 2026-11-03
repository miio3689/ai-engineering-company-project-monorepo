"""Resend email delivery for authentication messages."""

import html
import os

import resend

from .services_auth import PASSWORD_RESET_EXPIRE_MINUTES


class EmailServiceError(Exception):
    """Base error for controlled email delivery failures."""


class EmailConfigurationError(EmailServiceError):
    """Raised when required email delivery configuration is missing."""


class EmailDeliveryError(EmailServiceError):
    """Raised when the external email provider rejects or cannot deliver."""


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise EmailConfigurationError("El servicio de correo no está configurado.")

    resend.api_key = api_key
    sender = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
    safe_reset_url = html.escape(reset_url, quote=True)
    expiry_minutes = PASSWORD_RESET_EXPIRE_MINUTES
    message = {
        "from": sender,
        "to": [to_email],
        "subject": "Restablece tu contraseña de Brasaland",
        "html": (
            "<!doctype html><html lang=\"es\"><body style=\"margin:0;"
            "padding:24px;font-family:Arial,sans-serif;color:#1f2937;\">"
            "<main style=\"max-width:560px;margin:0 auto;line-height:1.6;\">"
            "<h1 style=\"font-size:24px;\">Restablece tu contraseña</h1>"
            "<p>Hemos recibido una solicitud para cambiar la contraseña de tu "
            "cuenta de Brasaland.</p>"
            f"<p><a href=\"{safe_reset_url}\" style=\"display:inline-block;"
            "padding:14px 22px;background:#c2410c;color:#ffffff;"
            "font-size:16px;text-decoration:none;border-radius:4px;\">"
            "Restablecer contraseña</a></p>"
            f"<p>Este enlace caduca en {expiry_minutes} minutos. "
            "Si no solicitaste el cambio, puedes ignorar este mensaje.</p>"
            "</main></body></html>"
        ),
        "text": (
            "Restablece tu contraseña de Brasaland\n\n"
            "Para elegir una contraseña nueva, abre este enlace:\n"
            f"{reset_url}\n\n"
            f"El enlace caduca en {expiry_minutes} minutos. "
            "Si no solicitaste el cambio, puedes ignorar este mensaje."
        ),
    }

    try:
        resend.Emails.send(message)
    except (resend.exceptions.ResendError, OSError) as exc:
        raise EmailDeliveryError("No se pudo entregar el correo.") from exc