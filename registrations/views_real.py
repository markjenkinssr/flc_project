from django.http import HttpResponse, JsonResponse, HttpRequest, HttpResponseRedirect
from django.urls import reverse

ACCESS_SESSION_KEY = "verified_email"

def sanity_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("<h1>✅ Django is working (real views)</h1>", content_type="text/html")

def user_access_view(request: HttpRequest) -> HttpResponse:
    email = request.GET.get("email")
    if email:
        request.session[ACCESS_SESSION_KEY] = email
        return HttpResponse("<h2>Access granted. Session set.</h2>", content_type="text/html")
    return HttpResponse("<h2>Access page — append ?email=test@example.com</h2>", content_type="text/html")

def registration_form_view(request: HttpRequest, user_id: int) -> HttpResponse:
    email = request.session.get(ACCESS_SESSION_KEY)
    if not email:
        return HttpResponseRedirect(reverse("registrations:user_access"))
    return HttpResponse("<h2>Registration form for user_id={}</h2>".format(user_id), content_type="text/html")

def finish_session_view(request: HttpRequest, user_id: int) -> HttpResponse:
    if ACCESS_SESSION_KEY in request.session:
        del request.session[ACCESS_SESSION_KEY]
    return HttpResponse("<h2>Finished session for user_id={}</h2>".format(user_id), content_type="text/html")

def manage_pending_users(request: HttpRequest) -> HttpResponse:
    return HttpResponse("<h2>Manage Pending Users (placeholder)</h2>", content_type="text/html")

def get_names_by_category(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"names": []})
