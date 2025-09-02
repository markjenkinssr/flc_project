from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

def registration_form_view(request: HttpRequest, user_id: int | None = None) -> HttpResponse:
    # Render your template as-is; only pass user_id in case the template references it.
    return render(request, "registrations/registration_form.html", {"user_id": user_id})
