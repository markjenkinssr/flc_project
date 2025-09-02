# registrations/email_utils.py

import os
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_email(
    subject: str,
    to_email: str | list[str],
    html_content: str,
    from_email: Optional[str] = None,
) -> int | None:
    sender = from_email or os.environ.get("DEFAULT_FROM_EMAIL", "noreply@example.com")
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        print("SendGrid error: SENDGRID_API_KEY is not set.")
        return None

    message = Mail(from_email=sender, to_emails=to_email, subject=subject, html_content=html_content)
    try:
        sg = SendGridAPIClient(api_key)
        resp = sg.send(message)
        return resp.status_code  # 202 == accepted
    except Exception as e:
        print(f"SendGrid error: {e}")
        return None
