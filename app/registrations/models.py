# registrations/models.py
from django.db import models
from django.utils import timezone
import uuid
from datetime import timedelta
from django.utils import timezone

class PendingUser(models.Model):
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    category = models.CharField(max_length=50)
    college_company = models.CharField(max_length=120, blank=True)

    # Validation flags
    is_validated = models.BooleanField(default=False)
    validated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.category})"



class FLCRegistration(models.Model):
    advisor = models.ForeignKey(
        "PendingUser",
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    first_name = models.CharField(max_length=120)
    last_name  = models.CharField(max_length=120)

    student_organization = models.CharField(max_length=120, blank=True)
    college_company      = models.CharField(max_length=120, blank=True)
    tour                 = models.CharField(max_length=120, blank=True)
    tee_shirt_size       = models.CharField(max_length=10, blank=True)
    food_allergy         = models.CharField(max_length=255, blank=True)
    ada_needs            = models.CharField(max_length=255, blank=True)

    # ✅ Safe fix: no prompt needed, works with old rows too
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class AccessLink(models.Model):
    """
    One-time, time-limited access links for PendingUsers.
    """
    token = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    @classmethod
    def create_for(cls, email, ttl_minutes=30):
        """Factory to generate a new access link with expiration."""
        return cls.objects.create(
            email=email,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )

    def is_valid(self):
        """Check if link is not used and has not expired."""
        return (not self.used) and timezone.now() < self.expires_at

    def __str__(self):
        status = "used" if self.used else "active"
        return f"AccessLink for {self.email} ({status}, expires {self.expires_at})"
