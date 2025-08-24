from django.core.mail import EmailMultiAlternatives

def send_html(to_email: str, subject: str, html: str, from_email: str | None = None) -> int:
    msg = EmailMultiAlternatives(subject=subject, body="", from_email=from_email, to=[to_email])
    msg.attach_alternative(html, "text/html")
    return msg.send(fail_silently=False)
