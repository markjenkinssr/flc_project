from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

try:
    from .models import PendingUser
except Exception:  # if model import fails, keep page rendering
    PendingUser = None  # type: ignore


def _field_names(model):
    try:
        return {f.name for f in model._meta.fields}
    except Exception:
        return set()

def sanity_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("<h1>✅ form view is live</h1>", content_type="text/html")


@require_http_methods(["GET", "POST"])
@csrf_protect
def registration_form_view(request: HttpRequest, user_id: int | None = None) -> HttpResponse:
    """
    Simple: add self + additional participants to PendingUser, then show list.
    Template stays unchanged: registrations/registration_form.html
    """
    categories = ["Student", "Advisor", "Sponsor", "Other"]
    just_added: list[str] = []
    errors: list[str] = []

    if request.method == "POST":
        if PendingUser is None:
            errors.append("PendingUser model not available.")
        else:
            email = (request.POST.get("email") or "").strip()
            if not email:
                errors.append("Primary email is required.")
            else:
                allowed = _field_names(PendingUser)
                base_payload = {
                    k: (request.POST.get(k) or "").strip()
                    for k in ["first_name", "last_name", "category", "college_company"]
                    if k in allowed
                }
                try:
                    with transaction.atomic():
                        # upsert primary person
                        obj, created = PendingUser.objects.get_or_create(email=email)
                        for k, v in base_payload.items():
                            setattr(obj, k, v)
                        obj.save()
                        just_added.append(email)

                        # additional participants
                        raw = (request.POST.get("participants_emails") or "").strip()
                        if raw:
                            import re
                            pieces = [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]
                            for pemail in pieces:
                                if pemail and "email" in _field_names(PendingUser):
                                    extra, _ = PendingUser.objects.get_or_create(
                                        email=pemail,
                                        defaults=base_payload
                                    )
                                    just_added.append(pemail)

                    if not errors:
                        messages.success(
                            request,
                            f"Saved {len(just_added)} entr{'y' if len(just_added)==1 else 'ies'}."
                        )
                except Exception as e:
                    errors.append(f"Save failed: {e}")

    # Always show the latest list (your template already has the bottom section)
    pending = []
    if PendingUser is not None:
        pending = list(PendingUser.objects.all().order_by("-id")[:100])

    ctx = {
        # Things your template commonly uses:
        "categories": categories,
        "names": [],
        # Lists for the bottom of the page (use both keys to match older/newer templates):
        "pending_users": pending,
        "recent_users": pending,
        # Optional: highlight what was just added this submit
        "just_added": just_added,
        "errors": errors,
    }
    return render(request, "registrations/registration_form.html", ctx)
