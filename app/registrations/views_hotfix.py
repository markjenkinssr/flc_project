from __future__ import annotations
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .models import PendingUser
from .constants import ACCESS_SESSION_KEY

def sanity_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("OK", content_type="text/plain")

@require_http_methods(["GET", "POST", "HEAD"])
def user_access_view(request: HttpRequest) -> HttpResponse:
    """
    Minimal, robust access handler:
    - Accepts ?email=... (GET) or POST email
    - If email exists in PendingUser, grant 30-day session and go straight to form/1/
    - Otherwise, render the original user_access template with a friendly message
    """
    email = (request.GET.get("email") or request.POST.get("email") or "").strip()
    if email:
        try:
            PendingUser.objects.get(email__iexact=email)
            request.session[ACCESS_SESSION_KEY] = email
            request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
            request.session.save()  # ensure sessionid cookie is issued immediately
            return redirect("registrations:registration_form", user_id=1)
        except PendingUser.DoesNotExist:
            messages.error(request, "Email not found. Please request access.")

    ctx = {
        # If your template expects these keys, they’re here.
        "categories": ["Student", "Advisor", "Community"],
        "names": [],
    }
    return render(request, "registrations/user_access.html", ctx)

def registration_form_view(request: HttpRequest, user_id: int) -> HttpResponse:
    # Render the actual form template you already have
    return render(request, "registrations/registration_form.html", {"user_id": user_id})

def finish_session_view(request: HttpRequest, user_id: int) -> HttpResponse:
    request.session.flush()
    messages.success(request, "Session cleared.")
    return redirect("registrations:user_access")

def manage_pending_users(request: HttpRequest) -> HttpResponse:
    # Show whatever the template expects; at minimum, pass the list
    pending_users = PendingUser.objects.order_by("-id")
    return render(request, "registrations/manage_pending_users.html", {"pending_users": pending_users})

def get_names_by_category(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"names": []})
