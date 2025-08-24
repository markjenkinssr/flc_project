# registrations/utils_tokens.py
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired

# Use a unique salt for this token type
SALT = "flc-email-verify"

_signer = signing.TimestampSigner(salt=SALT)

def make_validation_token(user_id: int, email: str) -> str:
    # Emails never contain ":", so a simple delimiter is fine
    return _signer.sign(f"{user_id}:{email}")

def read_validation_token(token: str, max_age_seconds: int = 7 * 24 * 60 * 60) -> tuple[int, str]:
    """
    Returns (user_id, email) or raises SignatureExpired / BadSignature.
    max_age_seconds defaults to 7 days.
    """
    raw = _signer.unsign(token, max_age=max_age_seconds)
    user_id_str, email = raw.split(":", 1)
    return int(user_id_str), email
