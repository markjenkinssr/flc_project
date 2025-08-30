from __future__ import annotations

from django.http import HttpResponse, JsonResponse, HttpRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.messages.api import MessageFailure
from django.urls import reverse

from .models import PendingUser, FLCRegistration
from .constants import ACCESS_SESSION_KEY


def _safe_message(request: HttpRequest, level: int, text: str):
    """Add a message if middleware is available; otherwise stash a one-off notice in session."""
    try:
        messages.add_message(request, level, text)
    except MessageFailure:
        # one-shot “flash” fallback
        request.session["_flash"] = text


def _consume_flash(request: HttpRequest):
    msg = request.session.pop("_flash", None)
    return msg


def sanity_view(request: HttpRequest):
    return HttpResponse("<h1>✅ Sanity OK</h1>", content_type="text/html")


def user_access_view(request: HttpRequest):
    """
    Accept ?email=... or POST email; if present in PendingUser, grant 30-day session and redirect in.
    Otherwise render the access page with categories.
    """
    email = (request.GET.get("email") or request.POST.get("email") or "").strip()

    if email:
        if PendingUser.objects.filter(email__iexact=email).exists():
            request.session[ACCESS_SESSION_KEY] = email
            request.session.set_expiry(30 * 24 * 3600)  # 30 days
            _safe_message(request, messages.SUCCESS, "Access granted.")
            return redirect("registrations:manage_pending_users")
        else:
            _safe_message(request, messages.ERROR, "Email not recognized. Please request access.")

    try:
        categories = list(
            PendingUser.objects
            .exclude(category__isnull=True)
            .exclude(category__exact="")
            .values_list("category", flat=True)
            .distinct()
            .order_by("category")
        ) or ["Student"]
    except Exception:
        categories = ["Student"]

    ctx = {
        "categories": categories,
        "names": [],
        "flash": _consume_flash(request),  # show fallback notice if needed
    }
    return render(request, "registrations/user_access.html", ctx)


def _require_access(request: HttpRequest):
    return request.session.get(ACCESS_SESSION_KEY)


def manage_pending_users(request: HttpRequest):
    verified_email = _require_access(request)
    if not verified_email:
        _safe_message(request, messages.INFO, "Please request access first.")
        return redirect("registrations:user_access")

    if hasattr(PendingUser, "created_at"):
        pending = PendingUser.objects.all().order_by("-created_at")
    else:
        pending = PendingUser.objects.all()

    ctx = {
        "verified_email": verified_email,
        "pending_users": pending,
        "flash": _consume_flash(request),
    }
    return render(request, "registrations/manage_pending_users.html", ctx)


def registration_form_view(request: HttpRequest, user_id: int):
    verified_email = _require_access(request)
    if not verified_email:
        _safe_message(request, messages.INFO, "Please request access first.")
        return redirect("registrations:user_access")

    user = get_object_or_404(PendingUser, id=user_id)
    ctx = {
        "user": user,
        "verified_email": verified_email,
        "flash": _consume_flash(request),
    }
    return render(request, "registrations/registration_form.html", ctx)


def finish_session_view(request: HttpRequest, user_id: int):
    request.session.pop(ACCESS_SESSION_KEY, None)
    _safe_message(request, messages.SUCCESS, "Your session has been cleared.")
    return render(request, "registrations/finish_session.html", {"user_id": user_id, "flash": _consume_flash(request)})


def get_names_by_category(request: HttpRequest):
    cat = (request.GET.get("category") or "").strip()
    qs = PendingUser.objects.all()
    if cat:
        qs = qs.filter(category__iexact=cat)

    names = [
        " ".join(p for p in [pu.first_name or "", pu.last_name or ""] if p).strip() or (pu.email or "")
        for pu in qs
    ]
    return JsonResponse({"names": names})
