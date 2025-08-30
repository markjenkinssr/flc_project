from django.views.decorators.http import require_http_methods
from django.template.response import TemplateResponse

@require_http_methods(["GET","HEAD","POST"])
def registration_form_view(request):
    # Minimal context so the template renders (no crashes)
    advisor = {
        "first_name": "Advisor",
        "last_name": "User",
        "id": 1,
        "registrations": [],  # keep empty for now to avoid attribute access issues
    }
    ctx = {
        "advisor": advisor,
        "fee": 25,
        "participant_count": 0,
        "total_cost": 0,
        "finish_session_url": "#summary",
        "form": {
            "first_name": '<input class="form-control" name="first_name" aria-label="First name">',
            "last_name": '<input class="form-control" name="last_name" aria-label="Last name">',
            "student_organization": '<input class="form-control" name="student_organization" aria-label="Student organization">',
            "college_company": '<input class="form-control" name="college_company" aria-label="College or company">',
            "tour": '<select class="form-select" name="tour" aria-label="Tour"><option value="">Select…</option><option>Campus</option><option>Lab</option></select>',
            "tee_shirt_size": '<select class="form-select" name="tee_shirt_size" aria-label="T-shirt size"><option value="">Select…</option><option>XS</option><option>S</option><option>M</option><option>L</option><option>XL</option></select>',
            "food_allergy": '<input class="form-control" name="food_allergy" aria-label="Food allergy">',
            "ada_needs": '<input class="form-control" name="ada_needs" aria-label="ADA needs">',
        },
    }
    return TemplateResponse(request, "registrations/registration_form.html", ctx)
