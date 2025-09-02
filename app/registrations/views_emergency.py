from __future__ import annotations
from django.http import HttpResponse
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt

try:
    from .models import PendingUser
except Exception:
    PendingUser = None  # if model import fails, we return a helpful message

def _rows(limit=200):
    if PendingUser is None:
        return []
    try:
        return list(PendingUser.objects.all().order_by("-id")[:limit])
    except Exception:
        return []

def _field(obj, name, default=""):
    try:
        return escape(getattr(obj, name, default) or default)
    except Exception:
        return default

def sanity(request):
    return HttpResponse("<h1>✅ Emergency layer is active</h1>", content_type="text/html; charset=utf-8")

@csrf_exempt
def manage_pending_users(request):
    """
    Minimal page: list last N PendingUser rows and allow adding one user.
    Accepts POST, but is CSRF-exempt to avoid middleware issues in prod.
    """
    msg = ""
    if request.method == "POST" and PendingUser:
        email = (request.POST.get("email") or "").strip().lower()
        first = request.POST.get("first_name", "") or ""
        last  = request.POST.get("last_name", "") or ""
        cat   = request.POST.get("category", "") or "Student"
        org   = request.POST.get("college_company", "") or ""
        if email:
            try:
                obj, created = PendingUser.objects.get_or_create(
                    email=email,
                    defaults={"first_name": first, "last_name": last, "category": cat, "college_company": org},
                )
                # best-effort update of optional fields
                for k, v in (("first_name", first), ("last_name", last), ("category", cat), ("college_company", org)):
                    try:
                        if hasattr(obj, k) and v and getattr(obj, k, "") != v:
                            setattr(obj, k, v)
                    except Exception:
                        pass
                try:
                    obj.save()
                except Exception:
                    pass
                msg = f"{'Added' if created else 'Updated'}: {escape(email)}"
            except Exception as e:
                msg = "DB error while saving"
        else:
            msg = "Email is required"

    rows = _rows()

    # Build a tiny HTML page by hand so nothing can go wrong
    html = []
    html.append("<!doctype html><meta charset='utf-8'><title>Manage Pending Users</title>")
    html.append("<h1>Manage Pending Users</h1>")
    if msg:
        html.append("<p><strong>" + escape(msg) + "</strong></p>")
    html.append("""
<form method="post" style="margin-bottom:16px;padding:12px;border:1px solid #ccc">
  <div><label>Email <input type="email" name="email" required></label></div>
  <div><label>First <input type="text" name="first_name"></label>
       <label>Last <input type="text" name="last_name"></label></div>
  <div><label>Category
        <select name="category">
          <option>Student</option><option>Faculty</option><option>Staff</option><option>Other</option>
        </select></label>
       <label>College/Company <input type="text" name="college_company"></label></div>
  <button type="submit">Save</button>
</form>
""")
    html.append("<table border='1' cellpadding='6'><tr><th>ID</th><th>Email</th><th>First</th><th>Last</th><th>Category</th><th>Org</th></tr>")
    for r in rows:
        html.append(
            "<tr>"
            f"<td>{_field(r,'id','')}</td>"
            f"<td>{_field(r,'email','')}</td>"
            f"<td>{_field(r,'first_name','')}</td>"
            f"<td>{_field(r,'last_name','')}</td>"
            f"<td>{_field(r,'category','')}</td>"
            f"<td>{_field(r,'college_company','')}</td>"
            "</tr>"
        )
    if not rows:
        html.append("<tr><td colspan='6'>No rows yet.</td></tr>")
    html.append("</table>")
    return HttpResponse("".join(html), content_type="text/html; charset=utf-8")

@csrf_exempt
def registration_form_basic(request):
    """
    Minimal registration form:
    - Adds the owner email.
    - Lets you add multiple participants (email + optional fields)
    """
    msg = ""
    saved = 0
    if request.method == "POST" and PendingUser:
        def save_one(email, first="", last="", cat="Student", org=""):
            nonlocal saved
            email = (email or "").strip().lower()
            if not email:
                return
            try:
                obj, created = PendingUser.objects.get_or_create(
                    email=email,
                    defaults={"first_name": first, "last_name": last, "category": cat, "college_company": org},
                )
                for k, v in (("first_name", first), ("last_name", last), ("category", cat), ("college_company", org)):
                    try:
                        if hasattr(obj, k) and v and getattr(obj, k, "") != v:
                            setattr(obj, k, v)
                    except Exception:
                        pass
                try:
                    obj.save()
                    saved += 1
                except Exception:
                    pass
            except Exception:
                pass

        # owner
        save_one(
            request.POST.get("owner_email"),
            request.POST.get("owner_first_name"),
            request.POST.get("owner_last_name"),
            request.POST.get("owner_category") or "Student",
            request.POST.get("owner_college_company"),
        )

        # participants arrays
        pe   = request.POST.getlist("participant_email[]")
        pf   = request.POST.getlist("participant_first_name[]")
        pl   = request.POST.getlist("participant_last_name[]")
        pcat = request.POST.getlist("participant_category[]")
        porg = request.POST.getlist("participant_college_company[]")
        for i, em in enumerate(pe[:20]):
            save_one(
                em,
                pf[i] if i < len(pf) else "",
                pl[i] if i < len(pl) else "",
                pcat[i] if i < len(pcat) else "Student",
                porg[i] if i < len(porg) else "",
            )
        msg = f"Saved {saved} entr{'y' if saved==1 else 'ies'}."

    # very small static form
    html = []
    html.append("<!doctype html><meta charset='utf-8'><title>Registration (Simple)</title>")
    html.append("<h1>Registration (Simple)</h1>")
    if msg: html.append("<p><strong>" + escape(msg) + "</strong></p>")
    html.append("""
<form method="post" style="margin-bottom:16px;padding:12px;border:1px solid #ccc">
  <fieldset><legend>Your info</legend>
    <div><label>Email <input type="email" name="owner_email" required></label></div>
    <div><label>First <input type="text" name="owner_first_name"></label>
         <label>Last <input type="text" name="owner_last_name"></label></div>
    <div><label>Category
          <select name="owner_category">
            <option>Student</option><option>Faculty</option><option>Staff</option><option>Other</option>
          </select></label>
         <label>College/Company <input type="text" name="owner_college_company"></label></div>
  </fieldset>

  <fieldset><legend>Additional participants</legend>
    <div id="participants"></div>
    <button type="button" onclick="addRow()">+ Add participant</button>
  </fieldset>

  <p><button type="submit">Submit</button></p>
</form>

<script>
function addRow(){
  const c=document.getElementById('participants');
  const d=document.createElement('div');
  d.style.cssText="margin:8px 0;padding:8px;border:1px solid #ccc";
  d.innerHTML = `
    <div><label>Email <input type="email" name="participant_email[]" required></label></div>
    <div><label>First <input type="text" name="participant_first_name[]"></label>
         <label>Last <input type="text" name="participant_last_name[]"></label></div>
    <div><label>Category
      <select name="participant_category[]">
        <option>Student</option><option>Faculty</option><option>Staff</option><option>Other</option>
      </select></label>
      <label>College/Company <input type="text" name="participant_college_company[]"></label></div>`;
  c.appendChild(d);
}
</script>
"""
    )
    # small list at bottom
    html.append("<h2>Recent Pending Users</h2>")
    html.append("<ul>")
    for r in _rows(50):
        html.append("<li>" + _field(r,"email","") + "</li>")
    html.append("</ul>")
    return HttpResponse("".join(html), content_type="text/html; charset=utf-8")
