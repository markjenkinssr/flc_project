from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

_signer = TimestampSigner()

def make_validation_token(user_id: int, email: str) -> str:
    return _signer.sign(f"{user_id}:{email}")

def read_validation_token(token: str, max_age_seconds: int):
    # returns (user_id:int, email:str) or raises
    raw = _signer.unsign(token, max_age=max_age_seconds)
    user_id_str, email = raw.split(":", 1)
    return int(user_id_str), email
