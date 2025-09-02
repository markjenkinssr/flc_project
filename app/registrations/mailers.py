from django.conf import settings
from django.core.mail import EmailMessage

def send_html(to_email: str, subject: str, html: str):
    email = EmailMessage(
        subject=subject,
        body=html,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[to_email],
    )
    email.content_subtype = "html"
    email.send(fail_silently=False)
