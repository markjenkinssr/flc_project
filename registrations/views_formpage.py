from __future__ import annotations
from typing import Any
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .forms_access import RegistrationForm
from .constants import ACCESS_SESSION_KEY

from .models import PendingUser, FLCRegistration  # existing app models

class _RegProxy:
    def __init__(self, qs):
        self._qs = qs
    def count(self):
        return self._qs.count()
    def all(self):
        return self._qs

def _get_or_set_advisor(request: HttpRequest) -> PendingUser | None:
    # allow quick session set via ?email=
    qemail = (request.GET.get("email") or "").strip()
    if qemail:
        request.session[ACCESS_SESSION_KEY] = qemail

    email = request.session.get(ACCESS_SESSION_KEY, "")
    if not email:
        return None
    advisor, _ = PendingUser.objects.get_or_create(email=email)
    return advisor

@require_http_methods(["GET", "POST"])
@csrf_protect
def registration_form_view(request: HttpRequest, user_id: int | None = None) -> HttpResponse:
    advisor = _get_or_set_advisor(request)
    if not advisor:
        messages.info(request, "Please provide ?email=you@example.com once to start.")
        return render(request, "registrations/registration_form.html", {
            "advisor": None,
            "form": RegistrationForm(),
            "fee": getattr(settings, "FLC_REG_FEE", 35),
            "participant_count": 0,
            "total_cost": 0,
            "finish_session_url": "#",
        }, status=200)

    # POST: add a participant
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                with transaction.atomic():
                    FLCRegistration.objects.create(
                        advisor=advisor,
                        first_name=data["first_name"],
                        last_name=data["last_name"],
                        student_organization=data.get("student_organization",""),
                        college_company=data.get("college_company",""),
                        tour=data.get("tour",""),
                        tee_shirt_size=data.get("tee_shirt_size",""),
                        food_allergy=data.get("food_allergy",""),
                        ada_needs=data.get("ada_needs",""),
                    )
                messages.success(request, "Participant added.")
                return redirect(reverse("registrations:registration_form"))
            except Exception as e:
                messages.error(request, f"Could not save: {e}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegistrationForm()

    # List current participants for this advisor
    qs = FLCRegistration.objects.filter(advisor=advisor).order_by("last_name","first_name")

    # Make template happy even if related_name differs
    advisor.registrations = _RegProxy(qs)  # type: ignore[attr-defined]

    fee = getattr(settings, "FLC_REG_FEE", 35)
    participant_count = qs.count()
    total_cost = participant_count * fee

    finish_url = reverse("registrations:finish_session", args=[advisor.id])

    ctx: dict[str, Any] = {
        "advisor": advisor,
        "form": form,
        "fee": fee,
        "participant_count": participant_count,
        "total_cost": total_cost,
        "finish_session_url": finish_url,
    }
    return render(request, "registrations/registration_form.html", ctx)
