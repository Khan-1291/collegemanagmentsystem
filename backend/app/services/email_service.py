import html
import json
import logging
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import BackgroundTasks

from app.config import settings

logger = logging.getLogger(__name__)
RESEND_EMAILS_URL = "https://api.resend.com/emails"


def email_layout(title: str, paragraphs: Sequence[str], footer: str = "") -> str:
    content = "".join(f"<p style=\"margin:0 0 16px;line-height:1.6\">{text}</p>" for text in paragraphs)
    footer_html = (
        f"<p style=\"margin:24px 0 0;color:#64748b;font-size:12px;line-height:1.5\">{footer}</p>"
        if footer
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"></head>
<body style="margin:0;background:#f4f7f6;padding:28px 12px;font-family:Arial,sans-serif;color:#17212b">
  <div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e1e8e5;border-radius:12px;overflow:hidden">
    <div style="background:#176b55;padding:20px 26px;color:#fff">
      <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.9">GPGCM · Computer Science</div>
      <div style="margin-top:8px;font-size:21px;font-weight:700">{html.escape(title)}</div>
    </div>
    <div style="padding:26px;font-size:15px">{content}{footer_html}</div>
    <div style="padding:14px 26px;background:#f8faf9;color:#64748b;font-size:11px">
      Government Post Graduate College Mardan · Computer Science Department
    </div>
  </div>
</body></html>"""


def send_email(recipient: str, subject: str, html_body: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.warning("Email not sent because RESEND_API_KEY is not configured.")
        return

    payload = json.dumps(
        {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [recipient],
            "subject": subject,
            "html": html_body,
        }
    ).encode("utf-8")
    request = Request(
        RESEND_EMAILS_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "GPGCM-CMS/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                logger.error("Resend rejected an email notification with HTTP %s.", response.status)
    except HTTPError as exc:
        logger.error("Resend rejected an email notification with HTTP %s.", exc.code)
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        logger.error("Email notification delivery failed: %s", exc.__class__.__name__)


def queue_email(
    background_tasks: BackgroundTasks,
    recipient: str,
    subject: str,
    title: str,
    paragraphs: Sequence[str],
    footer: str = "",
) -> None:
    if not settings.RESEND_API_KEY:
        logger.warning("Email notification skipped because RESEND_API_KEY is not configured.")
        return
    background_tasks.add_task(
        send_email,
        recipient,
        subject,
        email_layout(title, paragraphs, footer),
    )


def queue_welcome_email(
    background_tasks: BackgroundTasks,
    recipient: str,
    full_name: str,
    password: str,
) -> None:
    queue_email(
        background_tasks,
        recipient,
        "Your GPGCM portal account",
        "Welcome to the GPGCM portal",
        [
            f"Dear {html.escape(full_name)},",
            "Your college portal account has been created. Use the following credentials to sign in:",
            f"<strong>Email:</strong> {html.escape(recipient)}<br>"
            f"<strong>Initial password:</strong> {html.escape(password)}",
            f'<a href="{html.escape(settings.FRONTEND_BASE_URL, quote=True)}" '
            'style="display:inline-block;padding:11px 17px;background:#176b55;color:#fff;'
            'text-decoration:none;border-radius:7px">Open the college portal</a>',
        ],
        "Change your initial password after your first sign-in. If you did not expect this account, contact the department administrator.",
    )
