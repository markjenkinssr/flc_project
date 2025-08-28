from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .constants import ACCESS_SESSION_KEY
from .decorators import require_access
from .models import PendingUser


def sanity_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("sanity ok", content_type="text/html")


def user_access_view(request: HttpRequest) -> HttpResponse:
    """
    If ?email=... provided and found in PendingUser, set a 30-day session and
    send them to the registration form for that user.
    Otherwise, render the access page where they can enter an email.
    """
    email = (request.GET.get("email") or "").strip()
    if not email:
        ctx = {"categories": ["Student"], "names": []}
        return render(request, "registrations/user_access.html", ctx)

    user = PendingUser.objects.filter(email__iexact=email).first()
    if not user:
        messages.error(request, "Email not found. Please request access.")
        return redirect("registrations:user_access")

    # set session and extend expiry
    request.session[ACCESS_SESSION_KEY] = user.email
    request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
    messages.success(request, "Your email is confirmed. You can now register.")
    return redirect("registrations:registration_form", user_id=user.id)


@require_access
def registration_form_view(request: HttpRequest, user_id: int) -> HttpResponse:
    user = get_object_or_404(PendingUser, pk=user_id)
    return render(request, "registrations/registration_form.html", {"user": user})


@require_access
def finish_session_view(request: HttpRequest, user_id: int) -> HttpResponse:
    request.session.pop(ACCESS_SESSION_KEY, None)
    return render(request, "registrations/finish_session.html", {"user_id": user_id})


@require_access
def manage_pending_users(request: HttpRequest) -> HttpResponse:
    users = PendingUser.objects.all().order_by("last_name", "first_name")
    return render(request, "registrations/manage_pending_users.html", {"users": users})


def get_names_by_category(request: HttpRequest) -> JsonResponse:
    # Minimal stub — adjust if you have categories logic elsewhere
    return JsonResponse({"names": []})
PY