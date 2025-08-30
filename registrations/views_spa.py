from __future__ import annotations
from django import forms
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .models import PendingUser, FLCRegistration

# --- Form ---

TOUR_CHOICES = [
    ("Campus Tour A", "Campus Tour A"),
    ("Campus Tour B", "Campus Tour B"),
    ("Industry Tour", "Industry Tour"),
]

TEE_CHOICES = [
    ("XS", "XS"), ("S", "S"), ("M", "M"),
    ("L", "L"), ("XL", "XL"), ("2XL", "2XL"), ("3XL", "3XL"),
]

class RegistrationForm(forms.ModelForm):
    advisor_email = forms.EmailField(
        label="Advisor Email",
        help_text="All participants you add will be grouped under this email.",
        widget=forms.EmailInput(attrs={
            "aria-describedby": "advisorEmailHelp",
            "autocomplete": "email",
            "required": "required",
        }),
    )
    tour = forms.ChoiceField(choices=TOUR_CHOICES, required=False, label="Tour")
    tee_shirt_size = forms.ChoiceField(choices=TEE_CHOICES, required=False, label="T-Shirt Size")

    class Meta:
        model = FLCRegistration
        fields = [
            "first_name", "last_name",
            "student_organization", "college_company",
            "tour", "tee_shirt_size",
            "food_allergy", "ada_needs",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"required": "required", "aria-required": "true"}),
            "last_name": forms.TextInput(attrs={"required": "required", "aria-required": "true"}),
            "student_organization": forms.TextInput(),
            "college_company": forms.TextInput(),
            "food_allergy": forms.TextInput(attrs={"placeholder": "Leave blank if none"}),
            "ada_needs": forms.Textarea(attrs={"rows": 2, "placeholder": "Describe any ADA needs"}),
        }

def _advisor_fk_name() -> str:
    fks = [f.name for f in FLCRegistration._meta.get_fields()]
    for name in ("advisor", "pending_user"):
        if name in fks:
            return name
    return "advisor"

FK_NAME = _advisor_fk_name()

def _attach_advisor(reg: FLCRegistration, advisor: PendingUser) -> None:
    setattr(reg, FK_NAME, advisor)

def _registrations_for_advisor(advisor: PendingUser):
    return FLCRegistration.objects.filter(**{FK_NAME: advisor}).order_by("last_name", "first_name")

@require_http_methods(["GET", "HEAD", "POST"])
def registration_form_view(request: HttpRequest, advisor: str | None = None) -> HttpResponse:
    """
    One-page app:
      - Optional path param /registrations/form/<advisor>/
      - Or querystring ?advisor=
      - POST creates participant under advisor_email; redirect back to path URL (PRG)
    """
    # precedence: path advisor > ?advisor > posted advisor_email
    advisor_email = (advisor or request.GET.get("advisor") or request.POST.get("advisor_email") or "").strip().lower()

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            adv_email = form.cleaned_data["advisor_email"].strip().lower()
            advisor_obj, _ = PendingUser.objects.get_or_create(
                email=adv_email,
                defaults={"first_name": "", "last_name": "", "category": "Student"},
            )
            reg: FLCRegistration = form.save(commit=False)
            _attach_advisor(reg, advisor_obj)
            reg.save()
            messages.success(request, "Participant added.")
            # Prefer the path-style URL (no '?')
            return redirect(reverse("registrations:registration_form_advisor", args=[advisor_obj.email]))
    else:
        form = RegistrationForm(initial={"advisor_email": advisor_email} if advisor_email else None)

    advisor_obj = PendingUser.objects.filter(email=advisor_email).first() if advisor_email else None
    participants = _registrations_for_advisor(advisor_obj) if advisor_obj else []

    # Finish button: scroll to summary section on same page
    finish_url = (
        reverse("registrations:registration_form_advisor", args=[advisor_email]) + "#summary"
        if advisor_email else
        reverse("registrations:registration_form") + "#summary"
    )

    return render(request, "registrations/registration_form.html", {
        "form": form,
        "advisor": advisor_obj,
        "participants": participants,
        "advisor_email": advisor_email,
        "finish_url": finish_url,
    })
