from __future__ import annotations
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import escape
from django.db import transaction
from django.utils import timezone

# DB models
try:
    from .models import PendingUser, FLCRegistration
except Exception:  # very defensive
    PendingUser = None
    FLCRegistration = None

FEE = 40  # <-- changed from $25 to $40

# Simple option sets
TOUR_OPTIONS = [
    ("HB-CME", "Haley Barbour Center for Manufacturing Excellence"),
    ("Duff Center", "The Jim and Thomas Duff Center for Science and Technology Innovation"),
    ("None", "No Tour"),
]
TEE_OPTIONS = [
    ("", "Select size"),
    ("XS", "XS"), ("S", "S"), ("M", "M"), ("L", "L"), ("XL", "XL"), ("2XL", "2XL"),("3XL", "3XL"), ("4XL", "4XL"),
]
STUDENT_ORGANIZATION_OPTIONS = [
    ("DECA", "DECA"),
    ("FBLA", "Future Business Leaders of America"),
    ("SKILLSUSA", "SkillsUSA"),
    ("HOSA", "HOSA"),
    ("MCCB", "Mississippi Community College Board"),
    ("Other", "Other"),
]

COLLEGE_CHAPTER_OPTIONS = [
    ("Coahoma Community College", "Coahoma Community College"),
    ("Copiah-Lincoln Community College", "Copiah-Lincoln Community College"),
    ("Delta State University", "Delta State University"),
    ("East Central Community College", "East Central Community College"),
    ("East Mississippi Community College Mayhew", "East Mississippi Community College Mayhew"),
    ("East Mississippi Community College Scooba", "East Mississippi Community College Scooba"),
    ("Hinds Community College Raymond", "Hinds Community College Raymond"),
    ("Hinds Community College Utica", "Hinds Community College Utica"),
    ("Holmes Community College", "Holmes Community College"),
    ("Jones College", "Jones College"),
    ("Mississippi Delta Community College", "Mississippi Delta Community College"),
    ("Mississippi Gulf Coast Community College Harrison", "Mississippi Gulf Coast Community College Harrison"),
    ("Mississippi State University College of Business", "Mississippi State University College of Business"),
    ("Mississippi University for Women", "Mississippi University for Women"),
    ("Northeast Mississippi Community College", "Northeast Mississippi Community College"),
    ("Southwest Mississippi Community College", "Southwest Mississippi Community College"),
    ("Tougaloo College", "Tougaloo College"),
    ("University of Mississippi Desoto", "University of Mississippi Desoto"),
    ("Mississippi Community College Board", "Mississippi Community College Board"),
]

def _get_or_seed_advisor(email_hint: str|None) -> PendingUser|None:
    """Try to find an advisor (PendingUser). If none exists, seed a placeholder."""
    if PendingUser is None:
        return None
    qs = PendingUser.objects.all().order_by("id")
    if email_hint:
        found = PendingUser.objects.filter(email=email_hint).first()
        if found: 
            return found
    if qs.exists():
        return qs.first()
    # seed one minimal advisor
    return PendingUser.objects.create(
        email=email_hint or "web-seeded@example.com",
        first_name="Advisor",
        last_name="User",
        category="Advisor",
        college_company="MCCB",
        is_validated=True,
        validated_at=timezone.now(),
    )

def _html_input(name, label, value="", aria="", placeholder="", required=False):
    req = ' aria-required="true" required' if required else ""
    ph  = f' placeholder="{escape(placeholder)}"' if placeholder else ""
    return f"""
    <div class="col-6">
      <label class="form-label" for="{name}">{escape(label)}</label>
      <input id="{name}" name="{name}" class="form-control" type="text" value="{escape(value)}"{ph} {aria}{req}/>
    </div>"""

def _html_select(name, label, options, selected="", aria="", required=False):
    req = ' aria-required="true" required' if required else ""
    opts = []
    for v, text in options:
        sel = ' selected' if str(v) == str(selected) else ''
        opts.append(f'<option value="{escape(v)}"{sel}>{escape(text)}</option>')
    return f"""
    <div class="col-6">
      <label class="form-label" for="{name}">{escape(label)}</label>
      <select id="{name}" name="{name}" class="form-select" {aria}{req}>
        {''.join(opts)}
      </select>
    </div>"""

def _layout_css():
    return """<style>
    :root { --gap: 1.25rem; --pad: 1.25rem; }
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background:#fff; }
    .container { max-width: 960px; margin: 2rem auto; padding: 0 var(--pad); }
    .row { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); column-gap: var(--gap); row-gap: var(--gap); }
    .col-6 { grid-column: span 6; min-width: 0; }
    .col-12 { grid-column: span 12; }
    .right { text-align:right; }
    .card { border: 1px solid #ddd; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.06); background:#fff; }
    .card-header { padding: .9rem var(--pad); font-weight: 600; border-bottom: 1px solid #eee; }
    .card-body { padding: var(--pad); }
    .form-label { display:block; font-size:.9rem; margin-bottom:.35rem; }
    .form-control, .form-select { width:100%; padding:.6rem .75rem; border:1px solid #ccc; border-radius:8px; min-width:0; }
    .btn { display:inline-block; padding:.55rem .9rem; border-radius:10px; border:1px solid #0d6efd; background:#0d6efd; color:#fff; text-decoration:none; cursor:pointer; }
    .btn-success { border-color:#198754; background:#198754; }
    .alert { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.85rem var(--pad); border:1px solid #bfe3ff; background:#eaf6ff; border-radius:12px; }
    .table-responsive { overflow-x:auto; }
    table { width:100%; border-collapse: collapse; }
    th, td { padding:.7rem .6rem; border-bottom: 1px solid #eee; font-size:.95rem; }
    th { text-align:left; background:#fafafa; }
    .text-muted { color:#666; }
    @media (max-width: 768px) { .col-6 { grid-column: span 12; } .right { text-align:left; } }
    .msg { margin: .75rem 0; color:#0a58ca; }
    </style>"""

def _page_head(title="FLC Registration"):
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{escape(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  {_layout_css()}
</head>
<body>
<main class="container" role="main" aria-labelledby="pageTitle">
"""

def _page_foot():
    return "</main></body></html>"

@csrf_exempt
def registration_form_view(request: HttpRequest) -> HttpResponse:
    """Single-page add-participants form (DB-connected, minimal)."""
    email_hint = request.GET.get("email") or request.POST.get("email") or None
    advisor = _get_or_seed_advisor(email_hint)
    advisor_name = "Advisor User"
    if advisor:
        fn = getattr(advisor, "first_name", "") or ""
        ln = getattr(advisor, "last_name", "") or ""
        if fn or ln:
            advisor_name = f"{fn} {ln}".strip()

    message = ""
    if request.method == "POST" and FLCRegistration is not None and advisor is not None:
        # Read fields (all optional except essential ones)
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        student_organization = (request.POST.get("student_organization") or "").strip()
        college_company = (request.POST.get("college_company") or "").strip()
        tour = (request.POST.get("tour") or "").strip()
        tee_shirt_size = (request.POST.get("tee_shirt_size") or "").strip()
        food_allergy = (request.POST.get("food_allergy") or "").strip()
        ada_needs = (request.POST.get("ada_needs") or "").strip()

        if first_name and last_name:
            with transaction.atomic():
                FLCRegistration.objects.create(
                    advisor=advisor,
                    first_name=first_name,
                    last_name=last_name,
                    student_organization=student_organization,
                    college_company=college_company,
                    tour=tour,
                    tee_shirt_size=tee_shirt_size,
                    food_allergy=food_allergy,
                    ada_needs=ada_needs,
                    created_at=timezone.now(),
                )
            message = "Participant added."
        else:
            message = "First and Last name are required."

    # Pull current registrations for the advisor
    regs = []
    if FLCRegistration is not None and advisor is not None:
        regs = list(FLCRegistration.objects.filter(advisor=advisor).order_by("last_name", "first_name"))

    total_cost = (len(regs) * FEE)

    # Build HTML
    html = []
    html.append(_page_head("FLC Registration"))
    html.append(f"""
    <div class="row" style="align-items:center; margin-bottom:1rem;">
      <div class="col-6">
        <h1 id="pageTitle" class="h2" style="margin:0;">FLC Registration for {escape(advisor_name or "Advisor User")}</h1>
      </div>
      <div class="col-6 right">
        <a href="#summary" class="btn btn-success" aria-label="Finish and view summary">Finish &amp; Summary</a>
      </div>
    </div>

    <div class="alert" role="status" aria-live="polite">
      <div>
        Fee per participant: <strong>${FEE}</strong><br>
        Current total: <strong>{len(regs)} × ${FEE} = ${total_cost}</strong>
      </div>
    </div>
    """)
    if message:
        html.append(f'<div class="msg" role="status" aria-live="polite">{escape(message)}</div>')

    html.append("""
    <div class="card" aria-labelledby="addTitle">
      <div class="card-header" id="addTitle">Add Participant</div>
      <div class="card-body">
        <form method="post" novalidate aria-describedby="formHelp">
    """)
    # No CSRF (csrf_exempt view); keep it simple
    # Advisor email hint (hidden so posting preserves context)
    if advisor and getattr(advisor, "email", None):
        html.append(f'<input type="hidden" name="email" value="{escape(advisor.email)}"/>')

    # two-column grid, with dropdowns
    html.append('<div class="row">')
    html.append(_html_input("first_name", "First Name", required=True, aria=' aria-label="First Name"'))
    html.append(_html_input("last_name", "Last Name", required=True, aria=' aria-label="Last Name"'))

    html.append(_html_select("student_organization", "Student Organization", ORG_OPTIONS, aria=' aria-label="Student Organization"'))
    html.append(_html_select("college_company", "College/Company", COLLEGE_COMPANY_OPTIONS, aria=' aria-label="College or Company"'))

    html.append(_html_select("tour", "Tour", TOUR_OPTIONS, aria=' aria-label="Tour selection"'))
    html.append(_html_select("tee_shirt_size", "T-Shirt Size", TEE_OPTIONS, aria=' aria-label="T-Shirt Size"'))

    html.append(_html_input("food_allergy", "Food Allergy", placeholder="e.g., peanuts", aria=' aria-label="Food allergy (optional)"'))
    html.append(_html_input("ada_needs", "ADA/Accessibility Needs", placeholder="e.g., wheelchair access", aria=' aria-label="ADA needs (optional)"'))
    html.append('</div>')  # row

    html.append("""
          <div id="formHelp" class="text-muted" style="margin-top:.5rem;">Fields marked required must be completed.</div>
          <div style="margin-top:1rem;">
            <button type="submit" class="btn" aria-label="Add participant">Add Participant</button>
          </div>
        </form>
      </div>
    </div>
    """)

    # Summary table
    html.append(f"""
    <h2 class="h5" id="summary" style="margin-top:1.25rem;">Current Participants ({len(regs)})</h2>
    <div class="table-responsive" role="region" aria-label="Current Participants Table">
      <table role="table" aria-describedby="summary">
        <thead>
          <tr>
            <th role="columnheader">Name</th>
            <th role="columnheader">Student Org</th>
            <th role="columnheader">College/Company</th>
            <th role="columnheader">Tour</th>
            <th role="columnheader">Tee</th>
            <th role="columnheader">Fee</th>
          </tr>
        </thead>
        <tbody>
    """)
    if regs:
        for r in regs:
            html.append(f"""
          <tr>
            <td>{escape(r.first_name)} {escape(r.last_name)}</td>
            <td>{escape(r.student_organization or "")}</td>
            <td>{escape(r.college_company or "")}</td>
            <td>{escape(r.tour or "")}</td>
            <td>{escape(r.tee_shirt_size or "")}</td>
            <td>${FEE}</td>
          </tr>""")
    else:
        html.append("""<tr><td colspan="6" class="text-muted">No participants yet.</td></tr>""")
    html.append("""
        </tbody>
      </table>
    </div>
    """)
    html.append(_page_foot())
    return HttpResponse("".join(html))

@csrf_exempt
def manage_pending_users(request: HttpRequest) -> HttpResponse:
    """Tiny seeding page for PendingUser (email + names)."""
    notice = ""
    if PendingUser is not None and request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        college_company = (request.POST.get("college_company") or "").strip()
        if email:
            PendingUser.objects.get_or_create(
                email=email,
                defaults=dict(
                    first_name=first_name or "Advisor",
                    last_name=last_name or "User",
                    category="Advisor",
                    college_company=college_company or "MCCB",
                    is_validated=True,
                    validated_at=timezone.now(),
                ),
            )
            notice = f"Seeded/ensured: {email}"
        else:
            notice = "Email is required."

    users = []
    if PendingUser is not None:
        users = list(PendingUser.objects.all().order_by("id")[:100])

    html = []
    html.append(_page_head("Manage Pending Users"))
    if notice:
        html.append(f'<div class="msg" role="status" aria-live="polite">{escape(notice)}</div>')

    html.append("""
    <div class="card" aria-labelledby="seedTitle">
      <div class="card-header" id="seedTitle">Add/Ensure Advisor</div>
      <div class="card-body">
        <form method="post" novalidate>
          <div class="row">
            <div class="col-6">
              <label class="form-label" for="email">Email (required)</label>
              <input id="email" name="email" class="form-control" type="email" required aria-required="true"/>
            </div>
            <div class="col-6">
              <label class="form-label" for="college_company">College/Company</label>
              <select id="college_company" name="college_company" class="form-select" aria-label="College or Company">
                """ + "".join(f'<option value="{escape(v)}">{escape(t)}</option>' for v,t in COLLEGE_COMPANY_OPTIONS) + """
              </select>
            </div>
            <div class="col-6">
              <label class="form-label" for="first_name">First Name</label>
              <input id="first_name" name="first_name" class="form-control" type="text" />
            </div>
            <div class="col-6">
              <label class="form-label" for="last_name">Last Name</label>
              <input id="last_name" name="last_name" class="form-control" type="text" />
            </div>
          </div>
          <div style="margin-top:1rem;">
            <button type="submit" class="btn">Save</button>
          </div>
        </form>
      </div>
    </div>
    """)

    # list
    html.append("""
    <h2 class="h5" style="margin-top:1.25rem;">Existing Pending Users</h2>
    <div class="table-responsive">
      <table role="table">
        <thead>
          <tr><th>Email</th><th>Name</th><th>College/Company</th><th>Validated</th></tr>
        </thead>
        <tbody>
    """)
    if users:
        for u in users:
            name = f"{getattr(u, 'first_name','') or ''} {getattr(u, 'last_name','') or ''}".strip()
            html.append(f"<tr><td>{escape(u.email)}</td><td>{escape(name)}</td><td>{escape(getattr(u,'college_company','') or '')}</td><td>{'Yes' if getattr(u,'is_validated',False) else 'No'}</td></tr>")
    else:
        html.append('<tr><td colspan="4" class="text-muted">None</td></tr>')
    html.append("""
        </tbody>
      </table>
    </div>
    """)
    html.append(_page_foot())
    return HttpResponse("".join(html))

# Simple sanity
def sanity_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("<h1>✅ Simple views live</h1>", content_type="text/html")

# API stub (if you had a names endpoint earlier)
def get_names_by_category(request: HttpRequest) -> HttpResponse:
    return HttpResponse('{"names":[]}', content_type="application/json")
