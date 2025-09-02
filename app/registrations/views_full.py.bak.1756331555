from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse
from django.utils.html import escape
from django.utils import timezone
from django.core.signing import BadSignature, SignatureExpired

from .models import PendingUser, FLCRegistration
from .forms import AdvisorAccessForm, FLCRegistrationForm, PendingUserForm
from .constants import REG_FEE_PER_PERSON as FEE, ACCESS_SESSION_KEY, TOKEN_MAX_AGE_SECONDS
from .utils_tokens import make_validation_token, read_validation_token
from .mailers import send_html
from .decorators import require_access


# --- sanity ---
def sanity_view(request):
    return HttpResponse("<h1>✅ Django is working (server)</h1>", content_type="text/html")

# --- helpers ---
def _find_pending_user(category: str, name_value: str):
    if not category or not name_value:
        return None
    if name_value.isdigit():
        try:
            return PendingUser.objects.get(id=int(name_value), category=category)
        except PendingUser.DoesNotExist:
            return None
    parts = name_value.strip().split()
    if len(parts) >= 2:
        first, last = parts[0], " ".join(parts[1:])
        try:
            return PendingUser.objects.get(first_name=first, last_name=last, category=category)
        except PendingUser.DoesNotExist:
            return None
    return None

def _validation_link(request, user: PendingUser) -> str:
    token = make_validation_token(user.id, user.email)
    return request.build_absolute_uri(reverse("registrations:validate_user", args=[token]))

def _send_validation_email(request, user: PendingUser):
    link = _validation_link(request, user)
    html = f"""
    <p>Hello {escape(user.first_name)},</p>
    <p>Please confirm your email to access FLC Registration:</p>
    <p>
      <a href="{link}" style="display:inline-block;padding:10px 14px;background:#0d6efd;color:#fff;border-radius:6px;text-decoration:none;">
        Confirm Email
      </a>
    </p>
    <p>This link expires in 30 days.</p>
    """
    send_html(user.email, "Confirm your email for FLC Registration", html)

# --- pages ---
@csrf_protect
def user_access_view(request):
    """
    Shows AdvisorAccessForm. On POST, emails a validation link and takes the user
    to a 'check your email' page with a Resend option.
    """
    if request.method == "POST":
        form = AdvisorAccessForm(request.POST)
        category = (request.POST.get("category") or "").strip()
        name_val = (request.POST.get("name") or "").strip()

        user = _find_pending_user(category, name_val)
        if not user:
            messages.error(request, "Please select a valid category and name.")
            return render(request, "registrations/user_access.html", {"form": form})

        _send_validation_email(request, user)
        return redirect("registrations:confirmation_sent", email=user.email)

    form = AdvisorAccessForm()
    return render(request, "registrations/user_access.html", {"form": form})

def confirmation_sent(request, email: str):
    return render(request, "registrations/confirmation_sent.html", {"email": email})

@csrf_protect
def resend_confirmation(request):
    """
    POST {email} to re-send a validation email (throttle: 60s per email).
    """
    if request.method != "POST":
        return redirect("registrations:user_access")

    email = (request.POST.get("email") or "").strip()
    if not email:
        messages.error(request, "Missing email address.")
        return redirect("registrations:user_access")

    session_key = f"resent_ts::{email}"
    last_ts = request.session.get(session_key)
    now = timezone.now().timestamp()
    if last_ts and (now - float(last_ts) < 60):
        messages.warning(request, "Please wait a minute before requesting another email.")
        return redirect("registrations:confirmation_sent", email=email)

    try:
        user = PendingUser.objects.get(email=email)
    except PendingUser.DoesNotExist:
        messages.success(request, "If that email is registered, a confirmation has been sent.")
        return redirect("registrations:confirmation_sent", email=email)

    _send_validation_email(request, user)
    request.session[session_key] = str(now)
    messages.success(request, f"We’ve re-sent your confirmation to {email}.")
    return redirect("registrations:confirmation_sent", email=email)

def validate_user(request, token: str):
    try:
        user_id, email = read_validation_token(token, TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        messages.error(request, "Validation link expired. Please request a new one.")
        return redirect("registrations:user_access")
    except BadSignature:
        messages.error(request, "Invalid validation link.")
        return redirect("registrations:user_access")

    user = get_object_or_404(PendingUser, id=user_id, email=email)
    if not user.is_validated:
        user.is_validated = True
        user.validated_at = timezone.now()
        user.save(update_fields=["is_validated", "validated_at"])

    # allow multiple sessions by leaving the session cookie; you can adjust expiry as desired
    request.session[ACCESS_SESSION_KEY] = user.email
    # e.g., 12 hours: request.session.set_expiry(12 * 3600)
	request.session[ACCESS_SESSION_KEY] = user.email
	request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
	messages.success(request, "Your email is confirmed. You can now register.")
return redirect("registrations:registration_form", user_id=user.id)
    request.session.set_expiry(12 * 3600)

    messages.success(request, "Your email is confirmed. You can now register.")
    return redirect("registrations:registration_form", user_id=user.id)

@require_access
def registration_form_view(request, user_id: int):
    """
    Gated by session: email in session must match advisor.email.
    """
    advisor = get_object_or_404(PendingUser, id=user_id)

    sess_email = (request.session.get(ACCESS_SESSION_KEY) or "").lower()
    if sess_email != (advisor.email or "").lower():
        messages.error(request, "Please confirm your email first.")
        return redirect("registrations:user_access")

    if request.method == "POST":
        form = FLCRegistrationForm(request.POST)
        if form.is_valid():
            reg = form.save(commit=False)
            reg.advisor = advisor
            reg.save()
            messages.success(request, "Registration saved successfully!")
            return redirect("registrations:registration_form", user_id=advisor.id)
    else:
        form = FLCRegistrationForm()

    regs = advisor.registrations.order_by("last_name", "first_name")
    count = regs.count()
    total_cost = FEE * count

    return render(
        request,
        "registrations/registration_form.html",
        {
            "advisor": advisor,
            "form": form,
            "registrations": regs,
            "fee": FEE,
            "participant_count": count,
            "total_cost": total_cost,
        },
    )


@require_access
def finish_session_view(request, user_id: int):
    advisor = get_object_or_404(PendingUser, id=user_id)
    regs = advisor.registrations.order_by("last_name", "first_name")
    count = regs.count()
    total_cost = FEE * count
    return render(
        request,
        "registrations/finish_session.html",
        {"advisor": advisor, "registrations": regs, "fee": FEE, "participant_count": count, "total_cost": total_cost},
    )

def manage_pending_users(request):
    if request.method == "POST":
        form = PendingUserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pending user added.")
            return redirect("registrations:manage_pending_users")
    else:
        form = PendingUserForm()
    pending_users = PendingUser.objects.all().order_by("last_name", "first_name")
    return render(request, "registrations/manage_pending_users.html", {"form": form, "pending_users": pending_users})

def get_names_by_category(request):
    category = request.GET.get("category", "").strip()
    if not category:
        return JsonResponse({"names": []})
    users = (
        PendingUser.objects.filter(category=category)
        .order_by("first_name", "last_name")
        .values("id", "first_name", "last_name", "email")
    )
    names = [
        {"id": u["id"], "full_name": f'{u["first_name"]} {u["last_name"]}', "email": u["email"] or ""}
        for u in users
    ]
    return JsonResponse({"names": names})

# --- TEMP PLACEHOLDERS (remove once your real views are back) ---
from django.http import HttpResponse, JsonResponse

def user_access_view(request):
    return HttpResponse("<h2>Access page placeholder</h2>")

def registration_form_view(request, user_id: int):
    return HttpResponse(f"<h2>Registration form for user_id={user_id}</h2>")

def finish_session_view(request, user_id: int):
    return HttpResponse(f"<h2>Finish session for user_id={user_id}</h2>")

def manage_pending_users(request):
    return HttpResponse("<h2>Manage Pending Users placeholder</h2>")

def get_names_by_category(request):
    return JsonResponse({"names": []})
