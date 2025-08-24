# registrations/views.py
from __future__ import annotations

# stdlib
import csv
from io import StringIO

# django
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.core.signing import BadSignature, SignatureExpired
from django.views.decorators.http import require_http_methods, require_POST

# local
from .models import PendingUser, FLCRegistration
from .forms import (
    AdvisorAccessForm,
    PendingUserForm,
    FLCRegistrationForm,
    NewUserRequestForm,
    EventRegistrationForm,
    RequestAccessForm,
    CATEGORIES,
)
from .mailers import send_html
from .utils_tokens import make_validation_token, read_validation_token
from .constants import REG_FEE_PER_PERSON as FEE, ACCESS_SESSION_KEY
from .email_utils import send_email  # optional helper used in test_email_view

# ---------------------------------------------------------------------
# Basic pages
# ---------------------------------------------------------------------
@csrf_protect
def registration_edit_view(request, user_id: int, reg_id: int):
    """Edit a single participant for the given advisor."""
    advisor = get_object_or_404(PendingUser, id=user_id)
    reg = get_object_or_404(FLCRegistration, id=reg_id, advisor=advisor)

    if request.method == "POST":
        form = FLCRegistrationForm(request.POST, instance=reg)
        if form.is_valid():
            form.save()
            messages.success(request, "Participant updated.")
            return redirect("registrations:registration_form", user_id=advisor.id)
    else:
        form = FLCRegistrationForm(instance=reg)

    # Totals for header context
    count = advisor.registrations.count()
    total_cost = FEE * count
    finish_session_url = reverse("registrations:finish_session", kwargs={"user_id": advisor.id})

    return render(
        request,
        "registrations/registration_edit.html",
        {
            "form": form,
            "advisor": advisor,
            "advisor_id": advisor.id,
            "fee": FEE,
            "participant_count": count,
            "total_cost": total_cost,
            "finish_session_url": finish_session_url,
        },
    )


@require_http_methods(["POST"])
@csrf_protect
def registration_delete_view(request, user_id: int, reg_id: int):
    """Delete a single participant (POST-only)."""
    advisor = get_object_or_404(PendingUser, id=user_id)
    reg = get_object_or_404(FLCRegistration, id=reg_id, advisor=advisor)
    reg.delete()
    messages.success(request, "Participant deleted.")
    return redirect("registrations:registration_form", user_id=advisor.id)



@csrf_protect
def new_user_request_view(request):
    """
    Internal contact-style form for someone to request being added to PendingUser.
    Sends a simple email to staff and shows a success page.
    """
    if request.method == "POST":
        form = NewUserRequestForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                to_staff = getattr(settings, "STAFF_SUMMARY_EMAIL", "studentorgs@mccb.edu")
                subject = "FLC: New User Request"
                html = (
                    "<h3>New User Request</h3>"
                    f"<p><strong>Name:</strong> {escape(cd['first_name'])} {escape(cd['last_name'])}</p>"
                    f"<p><strong>Email:</strong> {escape(cd['email'])}</p>"
                    f"<p><strong>Category:</strong> {escape(cd['category'])}</p>"
                    f"<p><strong>Phone:</strong> {escape(cd.get('phone') or '-')}</p>"
                    f"<p><strong>Message:</strong><br>{escape(cd.get('message') or '-').replace('\\n','<br>')}</p>"
                )
                # Choose one helper:
                send_email(subject=subject, to_email=to_staff, html_content=html)
                # or: send_html(to_staff, subject, html)
            except Exception:
                # Don’t block user flow if email fails in dev.
                pass
            messages.success(request, "Your request has been submitted.")
            return redirect("registrations:request_success")
    else:
        form = NewUserRequestForm()

    return render(request, "registrations/new_user_request.html", {"form": form})

def sanity_view(request):
    return HttpResponse("<h1>✅ Django is working!</h1><p>You are on the sanity page.</p>")

def registration_home_view(request):
    return render(request, "registrations/home.html")

def forms_dashboard(request):
    return render(request, "registrations/forms_dashboard.html")

# ---------------------------------------------------------------------
# Request Access (public)
# ---------------------------------------------------------------------

@csrf_protect
def request_access_view(request):
    if request.method == "POST":
        form = RequestAccessForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            html = f"""
              <h3>New Access Request</h3>
              <p><strong>Name:</strong> {escape(cd['first_name'])} {escape(cd['last_name'])}</p>
              <p><strong>Email:</strong> {escape(cd['email'])}</p>
              <p><strong>Student Org:</strong> {escape(cd['student_organization'])}</p>
              <p><strong>College/Company:</strong> {escape(cd['college_company'])}</p>
              <p><strong>Cell:</strong> {escape(cd.get('phone') or '-')}</p>
              <p><strong>Message:</strong><br>{escape(cd.get('message') or '-').replace('\\n','<br>')}</p>
            """
            send_html(
                getattr(settings, "STAFF_SUMMARY_EMAIL", "studentorgs@mccb.edu"),
                "FLC: New User Access Request",
                html,
            )
            messages.success(request, "Thanks! Your request was sent to staff.")
            return redirect("registrations:request_access_success")
    else:
        form = RequestAccessForm()

    return render(
        request,
        "registrations/request_access.html",
        {"form": form, "HCAPTCHA_SITE_KEY": getattr(settings, "HCAPTCHA_SITE_KEY", "")},
    )

def request_access_success_view(request):
    return render(request, "registrations/request_access_success.html")

# ---------------------------------------------------------------------
# Validation (kept for later use, but NOT required right now)
# ---------------------------------------------------------------------

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
      <p>This link expires in 7 days.</p>
    """
    send_html(user.email, "Confirm your email for FLC Registration", html)

def validate_user(request, token: str):
    """Still available, but not required while validation is bypassed."""
    try:
        user_id, email = read_validation_token(token)
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

    # Set a session (useful later when you re-enable gating)
    request.session[ACCESS_SESSION_KEY] = user.email
    request.session.set_expiry(60 * 60)  # 1 hour

    messages.success(request, "Your email is confirmed. You can now register.")
    return redirect("registrations:registration_form", user_id=user.id)

@csrf_protect
def resend_validation(request, user_id: int):
    user = get_object_or_404(PendingUser, id=user_id)
    try:
        _send_validation_email(request, user)
        messages.success(request, f"Validation email re-sent to {user.email}.")
    except Exception as e:
        messages.error(request, f"Could not send validation email: {e}")
    return redirect("registrations:manage_pending_users")

@csrf_protect
def resend_confirmation(request):
    """Resend validation by email address (throttled)."""
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

    try:
        _send_validation_email(request, user)
        request.session[session_key] = str(now)
        messages.success(request, f"We’ve re-sent your confirmation to {email}.")
    except Exception as e:
        messages.error(request, f"Could not send the email right now. ({e})")

    return redirect("registrations:confirmation_sent", email=email)

def confirmation_sent(request, email):
    return render(request, "registrations/confirmation_sent.html", {"email": email})

# ---------------------------------------------------------------------
# Advisor Access -> Registration Form (validation bypassed for now)
# ---------------------------------------------------------------------

def _find_pending_user(category: str, name_value: str) -> PendingUser | None:
    """
    Expect 'name_value' to be the PendingUser.id.
    Returns a PendingUser or None.
    """
    if not category or not name_value or not name_value.isdigit():
        return None
    return PendingUser.objects.filter(id=int(name_value), category=category).first()

@csrf_protect
def user_access_view(request):
    if request.method == "POST":
        form = AdvisorAccessForm(request.POST)
        category = (request.POST.get("category") or "").strip()
        name_val = (request.POST.get("name") or "").strip()  # must be an ID

        user = _find_pending_user(category, name_val)
        if not user:
            messages.error(request, "Please select a valid category and name from the list.")
            return render(request, "registrations/user_access.html", {"form": form})

        # Directly allow access to the form (validation temporarily bypassed)
        return redirect("registrations:registration_form", user_id=user.id)

    # GET
    form = AdvisorAccessForm()
    return render(request, "registrations/user_access.html", {"form": form})

def get_names_by_category(request):
    category = (request.GET.get("category") or "").strip()
    if not category:
        return JsonResponse({"names": []})
    users = (
        PendingUser.objects.filter(category=category)
        .order_by("first_name", "last_name")
        .values("id", "first_name", "last_name", "email")
    )
    names = [
        {"id": u["id"], "full_name": f"{u['first_name']} {u['last_name']}", "email": u["email"]}
        for u in users
    ]
    return JsonResponse({"names": names})

# ---------------------------------------------------------------------
# Registration Form (no require_access while testing)
# ---------------------------------------------------------------------

@csrf_protect
def registration_form_view(request, user_id: int | None = None):
    if not user_id:
        messages.error(request, "Please select your account first.")
        return redirect("registrations:user_access")

    advisor = get_object_or_404(PendingUser, id=user_id)

    finish_session_url = reverse("registrations:finish_session", kwargs={"user_id": advisor.id})
    back_to_access_url = reverse("registrations:user_access")

    if request.method == "POST":
        form = FLCRegistrationForm(request.POST)
        if form.is_valid():
            reg = form.save(commit=False)
            reg.advisor = advisor
            reg.save()
            messages.success(request, "Registration saved successfully!")
            # Optional: email staff per-advisor CSV after each save
            _email_staff_summary_csv(advisor)
            return redirect("registrations:registration_form", user_id=advisor.id)
    else:
        form = FLCRegistrationForm()

    count = advisor.registrations.count()
    total_cost = FEE * count

    return render(
        request,
        "registrations/registration_form.html",
        {
            "form": form,
            "advisor": advisor,
            "advisor_id": advisor.id,
            "finish_session_url": finish_session_url,
            "back_to_access_url": back_to_access_url,
            "fee": FEE,
            "participant_count": count,
            "total_cost": total_cost,
        },
    )

def finish_session_view(request, user_id: int):
    advisor = get_object_or_404(PendingUser, id=user_id)
    regs = advisor.registrations.order_by("last_name", "first_name")
    count = regs.count()
    total_cost = FEE * count
    return render(
        request,
        "registrations/finish_session.html",
        {
            "advisor": advisor,
            "registrations": regs,
            "fee": FEE,
            "participant_count": count,
            "total_cost": total_cost,
        },
    )

# ---------------------------------------------------------------------
# Manage Pending Users + AJAX updates
# ---------------------------------------------------------------------

@csrf_protect
def manage_pending_users(request):
    """Create/list PendingUsers (optionally email validation link after create)."""
    if request.method == "POST":
        form = PendingUserForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            try:
                # Optional: send validation email even while bypassed
                _send_validation_email(request, new_user)
                messages.success(request, "Pending user added and validation email sent.")
            except Exception:
                messages.warning(request, "User added, but validation email could not be sent right now.")
            return redirect("registrations:manage_pending_users")
    else:
        form = PendingUserForm()

    pending_users = PendingUser.objects.all().order_by("last_name", "first_name")
    category_values = [c[0] if isinstance(c, (list, tuple)) else c for c in CATEGORIES]

    return render(
        request,
        "registrations/manage_pending_users.html",
        {"form": form, "pending_users": pending_users, "CATEGORIES": category_values},
    )

@csrf_exempt
def update_pending_user(request, user_id: int):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"})
    try:
        user = PendingUser.objects.get(id=user_id)
    except PendingUser.DoesNotExist:
        return JsonResponse({"success": False, "error": "User not found"})
    form = PendingUserForm(request.POST, instance=user)
    if form.is_valid():
        form.save()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "errors": form.errors})

@csrf_exempt
def delete_pending_user(request, user_id: int):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"})
    try:
        user = PendingUser.objects.get(id=user_id)
        user.delete()
        return JsonResponse({"success": True})
    except PendingUser.DoesNotExist:
        return JsonResponse({"success": False, "error": "User not found"})

# ---------------------------------------------------------------------
# CSV Reports (per-advisor email helper + global CSV/email)
# ---------------------------------------------------------------------

def _email_staff_summary_csv(advisor: PendingUser) -> None:
    """Per-advisor CSV attachment with fee and totals."""
    rows = FLCRegistration.objects.filter(advisor=advisor).order_by("last_name", "first_name")

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(
        ["First Name", "Last Name", "Student Org", "College/Company", "Tour", "Tee", "Allergy", "ADA", "FeeUSD"]
    )
    for r in rows:
        writer.writerow([
            r.first_name,
            r.last_name,
            getattr(r, "student_organization", ""),
            getattr(r, "college_company", ""),
            getattr(r, "tour", ""),
            getattr(r, "tee_shirt_size", ""),
            getattr(r, "food_allergy", ""),
            getattr(r, "ada_needs", ""),
            f"{FEE:.2f}",
        ])

    count = rows.count()
    total_cost = FEE * count
    writer.writerow([])
    writer.writerow(["Total participants", count])
    writer.writerow(["Total cost (USD)", f"{total_cost:.2f}"])

    to_email = getattr(settings, "STAFF_SUMMARY_EMAIL", "studentorgs@mccb.edu")
    subject = f"FLC Registration Update: {advisor.first_name} {advisor.last_name} ({advisor.email})"
    body = (
        f"Participant list update for {advisor.first_name} {advisor.last_name} "
        f"in category {advisor.category}. Total participants: {count}. Total cost: ${total_cost:.2f}."
    )

    try:
        from django.core.mail import EmailMessage
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[to_email],
        )
        email.attach(filename="participants.csv", content=sio.getvalue(), mimetype="text/csv")
        email.send(fail_silently=True)
    except Exception:
        # don't block the flow on email issues
        pass

def download_all_registrations_csv(request):
    """CSV of ALL participants with fee and grand totals."""
    qs = (
        FLCRegistration.objects
        .select_related("advisor")
        .order_by("advisor__last_name", "advisor__first_name", "last_name", "first_name")
    )

    sio = StringIO()
    w = csv.writer(sio)
    w.writerow([
        "Advisor Email", "Advisor First", "Advisor Last", "Category",
        "Participant First", "Participant Last", "Student Org", "College/Company",
        "Tour", "Tee", "Allergy", "ADA", "FeeUSD"
    ])

    total_count = 0
    for r in qs:
        w.writerow([
            r.advisor.email,
            r.advisor.first_name,
            r.advisor.last_name,
            r.advisor.category,
            r.first_name,
            r.last_name,
            getattr(r, "student_organization", ""),
            getattr(r, "college_company", ""),
            getattr(r, "tour", ""),
            getattr(r, "tee_shirt_size", ""),
            getattr(r, "food_allergy", ""),
            getattr(r, "ada_needs", ""),
            f"{FEE:.2f}",
        ])
        total_count += 1

    total_cost = FEE * total_count
    w.writerow([])
    w.writerow(["Total participants", total_count])
    w.writerow(["Total cost (USD)", f"{total_cost:.2f}"])

    response = HttpResponse(sio.getvalue().encode("utf-8"), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename=\"flc_all_registrations.csv\"'
    return response

def email_all_registrations_csv(request):
    """Email the combined CSV to staff."""
    qs = (
        FLCRegistration.objects
        .select_related("advisor")
        .order_by("advisor__last_name", "advisor__first_name", "last_name", "first_name")
    )

    sio = StringIO()
    w = csv.writer(sio)
    w.writerow([
        "Advisor Email", "Advisor First", "Advisor Last", "Category",
        "Participant First", "Participant Last", "Student Org", "College/Company",
        "Tour", "Tee", "Allergy", "ADA", "FeeUSD"
    ])

    total_count = 0
    for r in qs:
        w.writerow([
            r.advisor.email,
            r.advisor.first_name,
            r.advisor.last_name,
            r.advisor.category,
            r.first_name,
            r.last_name,
            getattr(r, "student_organization", ""),
            getattr(r, "college_company", ""),
            getattr(r, "tour", ""),
            getattr(r, "tee_shirt_size", ""),
            getattr(r, "food_allergy", ""),
            getattr(r, "ada_needs", ""),
            f"{FEE:.2f}",
        ])
        total_count += 1

    total_cost = FEE * total_count
    subject = "FLC: All Registrations CSV"
    body = f"Attached is the combined registrations CSV. Total participants: {total_count}. Total cost: ${total_cost:.2f}."
    to_email = getattr(settings, "STAFF_SUMMARY_EMAIL", "studentorgs@mccb.edu")

    try:
        from django.core.mail import EmailMessage
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[to_email],
        )
        email.attach(filename="flc_all_registrations.csv", content=sio.getvalue(), mimetype="text/csv")
        email.send(fail_silently=False)
        messages.success(request, "Combined CSV emailed to staff.")
    except Exception as e:
        messages.error(request, f"Could not send email: {e}")

    return redirect("registrations:forms_dashboard")

# ---------------------------------------------------------------------
# Optional: event registration & simple email test
# ---------------------------------------------------------------------

@csrf_protect
def event_registration_view(request):
    if request.method == "POST":
        form = EventRegistrationForm(request.POST)
        if form.is_valid():
            selected_user = form.cleaned_data.get("user")
            messages.success(request, f"Event registration for {selected_user} completed.")
            if hasattr(selected_user, "email") and selected_user.email:
                send_email(
                    subject="FLC Event Registration",
                    to_email=selected_user.email,
                    html_content="<p>Your event registration is complete.</p>",
                )
            return redirect("registrations:registration_success")
    else:
        form = EventRegistrationForm()
    return render(request, "registrations/event_registration.html", {"form": form})

def registration_success_view(request):
    return render(request, "registrations/confirmation.html")

def request_success_view(request):
    return render(request, "registrations/request_confirmation.html")

# ---------------------------------------------------------------------
# Dev-only quick add page (no templates) – remove when not needed
# ---------------------------------------------------------------------

CATEGORIES_INLINE = [
    "Advisors","Vendors","Speakers","Guests","Staff","Sponsors","Students","Parents",
    "Chaperones","Volunteers","Press","VIP","Alumni","Board","Partners","VIC","General"
]

@csrf_exempt
def quick_add_pending_user(request):
    msg = ""
    if request.method == "POST":
        first = request.POST.get("first_name", "").strip()
        last = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        category = request.POST.get("category", "").strip()
        if not (first and last and email and category):
            msg = "<div style='color:#b02a37;margin:8px 0;'>All fields are required.</div>"
        else:
            obj, created = PendingUser.objects.get_or_create(
                email=email,
                defaults={"first_name": first, "last_name": last, "category": category},
            )
            if created:
                msg = f"<div style='color:#0a7c3b;margin:8px 0;'>Added {escape(first)} {escape(last)} ({escape(email)})</div>"
            else:
                obj.first_name = first
                obj.last_name = last
                obj.category = category
                obj.save()
                msg = f"<div style='color:#0a7c3b;margin:8px 0;'>Updated {escape(first)} {escape(last)} ({escape(email)})</div>"

    rows = []
    for p in PendingUser.objects.all().order_by("last_name", "first_name"):
        rows.append(
            f"<tr><td>{escape(p.first_name)}</td><td>{escape(p.last_name)}</td>"
            f"<td>{escape(p.email)}</td><td>{escape(p.category)}</td></tr>"
        )
    options = "".join(f"<option value='{escape(c)}'>{escape(c)}</option>" for c in CATEGORIES_INLINE)

    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Quick Add Pending Users</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
    label {{ display:block; font-weight:600; margin-top:12px; }}
    input, select {{ padding:8px; width: 280px; max-width: 100%; }}
    button {{ margin-top:16px; padding:10px 16px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; }}
    th {{ background:#f5f5f5; text-align:left; }}
  </style>
</head>
<body>
  <h1>Quick Add Pending Users</h1>
  <p><em>Dev-only page that bypasses templates.</em></p>
  {msg}
  <form method="post">
    <label>First Name</label>
    <input name="first_name" required>
    <label>Last Name</label>
    <input name="last_name" required>
    <label>Email</label>
    <input name="email" type="email" required>
    <label>Category</label>
    <select name="category" required>
      <option value="">— Select —</option>
      {options}
    </select>
    <br>
    <button type="submit">Save</button>
  </form>

  <h2>Current Pending Users</h2>
  <table>
    <thead><tr><th>First</th><th>Last</th><th>Email</th><th>Category</th></tr></thead>
    <tbody>
      {''.join(rows) if rows else "<tr><td colspan='4'>No pending users yet.</td></tr>"}
    </tbody>
  </table>
</body>
</html>
"""
    return HttpResponse(html)
