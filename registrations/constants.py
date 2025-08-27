from decimal import Decimal

# Session key used to store the validated email
ACCESS_SESSION_KEY = "verified_email"

# Per-person fee
REG_FEE_PER_PERSON = Decimal("40.00")

# Validation token lifetime: 30 days
TOKEN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
