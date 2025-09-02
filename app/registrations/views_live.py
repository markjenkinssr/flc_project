from django.http import HttpResponse, JsonResponse, HttpResponseNotFound
from django.shortcuts import render, redirect
from django.template import TemplateDoesNotExist

# session key for verified access (fallback if constants.py missing)
try:
    from .constants import ACCESS_SESSION_KEY
except Exception:
    ACCESS_SESSION_KEY = "verified_email"

# Try to import your models; if not present we’ll still serve placeholders.
PendingUser = FLCRegistration = AccessLink = None
try:
    from .models import PendingUser, FLCRegistration, AccessLink  # type: ignore
except Exception:
    pass

def _safe_render(request, template_name, context):
    """Try to render a template; if it doesn't exist, return a simple fallback."""
    try:
        return render(request, template_name, context)
    except TemplateDoesNotExist:
        # simple, never-500 fallback
        body = ["<h2>Template not found:</h2>", f"<code>{template_name}</code>", "<hr>"]
        for k, v in context.items():
            body.append(f"<p><strong>{k}</strong>: {v!r}</p>")
        return HttpResponse("\n".join(body), content_type="text/html")

def sanity_view(request):
    return HttpResponse("<h1>✅ App is online</h1>", content_type="text/html")

def user_access_view(request):
    """
    Entry screen where users pick their name/category and get access.
    If templates exist, uses them; otherwise shows a simple placeholder.
    """
    categories = []
    names = []
    if PendingUser:
        try:
            categories = (
                PendingUser.objects.values_list("category", flat=True)
                .distinct()
                .order_by("category")
            )
        except Exception:
            pass

    ctx = {"categories": list(categories), "names": names}
    return _safe_render(request, "registrations/user_access.html", ctx)

def get_names_by_category(request):
    """AJAX helper for the access page."""
    cat = request.GET.get("category") or ""
    results = []
    if PendingUser and cat:
        try:
            qs = PendingUser.objects.filter(category=cat).order_by("last_name", "first_name")
            results = [
                {"id": u.id, "name": f"{u.first_name} {u.last_name}".strip()}
                for u in qs
            ]
        except Exception:
            pass
    return JsonResponse({"names": results})

def _require_access(request):
    """Return None if access is OK; otherwise an HttpResponse that redirects to access page."""
    if request.session.get(ACCESS_SESSION_KEY):
        return None
    # Gentle message with a link so users know what to do
    return HttpResponse(
        "<h3>Access required</h3><p>Please start at <a href='/registrations/user-access/'>User Access</a>.</p>",
        content_type="text/html",
        status=401,
    )

def registration_form_view(request, user_id: int):
    """Main registration form page for a selected user."""
    need = _require_access(request)
    if need:
        return need

    user = None
    if PendingUser:
        try:
            user = PendingUser.objects.filter(id=user_id).first()
        except Exception:
            user = None

    if not user:
        return HttpResponseNotFound("<h3>Unknown user</h3>")

    ctx = {"user": user}
    return _safe_render(request, "registrations/registration_form.html", ctx)

def finish_session_view(request, user_id: int):
    """Finish/clear session and send the user back to the access page."""
    request.session.pop(ACCESS_SESSION_KEY, None)
    return redirect("/registrations/user-access/")

def manage_pending_users(request):
    """Simple management page (placeholder unless template exists)."""
    users = []
    if PendingUser:
        try:
            users = list(PendingUser.objects.order_by("-id")[:200])
        except Exception:
            pass
    ctx = {"users": users}
    return _safe_render(request, "registrations/manage_pending_users.html", ctx)
