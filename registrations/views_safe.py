from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

# Import models if present; keep views working even if one is missing
try:
    from .models import PendingUser, FLCRegistration
except Exception:  # noqa: BLE001
    PendingUser = None  # type: ignore
    FLCRegistration = None  # type: ignore


def _field_names(model):
    try:
        return {f.name for f in model._meta.fields}
    except Exception:
        return set()

def sanity_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("<h1>✅ Safe views online</h1>", content_type="text/html")


@require_http_methods(["GET", "POST"])
@csrf_protect
def manage_pending_users(request: HttpRequest) -> HttpResponse:
    """
    Minimal, robust 'seed users' page:
    - GET: render your existing template
    - POST: create/update PendingUser for the primary email
            and (optionally) create additional PendingUsers from a
            comma/space/newline-separated list.
    """
    categories = ["Student", "Advisor", "Sponsor", "Other"]  # used by original template
    created = updated = extras = 0
    errors = []

    if request.method == "POST":
        if PendingUser is None:
            messages.error(request, "PendingUser model not available.")
            return render(request, "registrations/manage_pending_users.html",
                          {"categories": categories, "errors": errors})

        email = (request.POST.get("email") or "").strip()
        if not email:
            errors.append("Primary email is required.")
        else:
            # Build dict with only fields that exist in your model
            allowed = _field_names(PendingUser)
            payload = {k: (request.POST.get(k) or "").strip()
                       for k in ["first_name", "last_name", "category", "college_company", "email"]
                       if k in allowed}

            try:
                with transaction.atomic():
                    obj, is_created = PendingUser.objects.get_or_create(email=email)
                    for k, v in payload.items():
                        setattr(obj, k, v)
                    obj.save()
                    created += 1 if is_created else 0
                    updated += 0 if is_created else 1

                    # Additional participants: create PendingUser rows for each email
                    raw = request.POST.get("participants_emails", "")
                    if raw:
                        import re
                        parts = [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]
                        extras_payload = {k: v for k, v in payload.items() if k != "email"}
                        for pemail in parts:
                            if "email" in allowed and pemail:
                                extra, _ = PendingUser.objects.get_or_create(email=pemail, defaults=extras_payload)
                                extras += 1
                if not errors:
                    msg = []
                    if created: msg.append(f"{created} added")
                    if updated: msg.append(f"{updated} updated")
                    if extras:  msg.append(f"{extras} additional")
                    messages.success(request, "Pending users saved (" + ", ".join(msg) + ").")
            except Exception as e:  # noqa: BLE001
                errors.append(f"Save failed: {e}")

    ctx = {
        "categories": categories,
        "errors": errors,
        # Your template often lists existing users:
        "pending_users": PendingUser.objects.all().order_by("-id")[:50] if PendingUser else [],
    }
    return render(request, "registrations/manage_pending_users.html", ctx)


@require_http_methods(["GET", "POST"])
@csrf_protect
def registration_form_view(request: HttpRequest, user_id: int | None = None) -> HttpResponse:
    """
    Show the original registration form and (on POST) attempt to save a registration
    using only the fields that actually exist on FLCRegistration.
    """
    pending_user = None
    if PendingUser and user_id:
        pending_user = get_object_or_404(PendingUser, pk=user_id)

    if request.method == "POST":
        if FLCRegistration is None:
            messages.error(request, "Registration model not available; nothing was saved.")
        else:
            allowed = _field_names(FLCRegistration) - {"id"}
            data = {k: v for k, v in request.POST.items() if k in allowed}
            # If your model expects a foreign key to PendingUser, try reasonable names:
            if pending_user:
                for fk_name in ["pending_user", "advisor", "user", "owner"]:
                    if fk_name in allowed:
                        data[fk_name + "_id"] = pending_user.id  # pass fk as *_id
                        break
            try:
                with transaction.atomic():
                    FLCRegistration.objects.create(**data)
                messages.success(request, "Registration submitted.")
                return redirect(request.path)  # PRG pattern
            except Exception as e:  # noqa: BLE001
                messages.error(request, f"Save failed: {e}")

    # Context the original template expects
    ctx = {
        "user": pending_user,                 # many templates expect {{ user }}
        "pending_user": pending_user,         # and/or {{ pending_user }}
        "categories": ["Student", "Advisor", "Sponsor", "Other"],
        "names": [],                          # used by AJAX names in some versions
    }
    return render(request, "registrations/registration_form.html", ctx)


def get_names_by_category(request: HttpRequest) -> JsonResponse:
    cat = (request.GET.get("category") or "").strip()
    names = []
    if PendingUser and cat:
        qs = PendingUser.objects.filter(category=cat).values("first_name", "last_name", "email")[:50]
        for row in qs:
            fn = (row.get("first_name") or "").strip()
            ln = (row.get("last_name") or "").strip()
            display = (" ".join([fn, ln]).strip() or row.get("email") or "").strip()
            if display:
                names.append(display)
    return JsonResponse({"names": names})
