from __future__ import annotations
from django.http import HttpResponse, JsonResponse, HttpRequest
from django.shortcuts import render

def sanity_view(request: HttpRequest):
    return HttpResponse("<h1>✅ Rescue sanity OK</h1>", content_type="text/html")

def user_access_view(request: HttpRequest):
    # Minimal context so your template renders
    ctx = {"categories": ["Student"], "names": []}
    return render(request, "registrations/user_access.html", ctx)

def registration_form_view(request: HttpRequest, user_id: int):
    return render(request, "registrations/registration_form.html", {"user_id": user_id})

def finish_session_view(request: HttpRequest, user_id: int):
    return render(request, "registrations/finish_session.html", {"user_id": user_id})

def manage_pending_users(request: HttpRequest):
    return render(request, "registrations/manage_pending_users.html", {})

def get_names_by_category(request: HttpRequest):
    return JsonResponse({"names": []})
