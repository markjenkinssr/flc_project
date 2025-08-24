# registrations/forms.py
from django import forms
from .models import PendingUser, FLCRegistration

# -----------------------------
# Hardcoded choices (single source of truth)
# -----------------------------
CATEGORIES = [
    ("DECA", "DECA"),
    ("FBLA", "FBLA"),
    ("SkillsUSA", "SkillsUSA"),
    ("HOSA", "HOSA"),
    ("Staff", "Staff"),
    ("Vendor", "Vendor"),
    ("Student", "Student"),
    ("Guest", "Guest"),
]

STUDENT_ORGS = [
    ("DECA", "DECA"),
    ("FBLA", "FBLA"),
    ("SkillsUSA", "SkillsUSA"),
    ("HOSA", "HOSA"),
    ("Mississippi Postsecondary Student Organizations", "Mississippi Postsecondary Student Organizations"),
]

COLLEGE_COMPANIES = [
    ("Coahoma Community College", "Coahoma Community College"),
    ("Copiah-Lincoln Community College", "Copiah-Lincoln Community College"),
    ("East Central Community College", "East Central Community College"),
    ("East Mississippi Community College", "East Mississippi Community College"),
    ("Hinds Community College", "Hinds Community College"),
    ("Holmes Community College", "Holmes Community College"),
    ("Itawamba Community College", "Itawamba Community College"),
    ("Jones College", "Jones College"),
    ("Meridian Community College", "Meridian Community College"),
    ("Mississippi Delta Community College", "Mississippi Delta Community College"),
    ("Mississippi Gulf Coast Community College", "Mississippi Gulf Coast Community College"),
    ("Northeast Mississippi Community College", "Northeast Mississippi Community College"),
    ("Northwest Mississippi Community College", "Northwest Mississippi Community College"),
    ("Pearl River Community College", "Pearl River Community College"),
    ("Southwest Mississippi Community College", "Southwest Mississippi Community College"),
    ("Mississippi Community College Board", "Mississippi Community College Board"),
    ("Other", "Other"),
]

TEE_SIZES = [
    ("S", "Small"),
    ("M", "Medium"),
    ("L", "Large"),
    ("XL", "XL"),
    ("2XL", "2XL"),
    ("3XL", "3XL"),
    ("4XL", "4XL"),
]

TOURS = [
    ("HB-CME", "Haley Barbour Center for Manufacturing Excellence"),
    ("None", "No Tour"),
]

# -----------------------------
# Forms
# -----------------------------

class AdvisorAccessForm(forms.Form):
    """Start point: select Category, then Name via AJAX; email is read-only helper."""
    category = forms.ChoiceField(
        choices=[("", "— Select —")] + CATEGORIES,
        label="Category",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    name = forms.ChoiceField(
        choices=[("", "— Select —")],
        label="Select Name",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    email = forms.EmailField(
        required=False,
        label="Email",
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"})
    )


class PendingUserForm(forms.ModelForm):
    """Admin/staff add a pending user (dropdowns enforce fixed vocab)."""
    category = forms.ChoiceField(
        choices=[("", "— Select —")] + CATEGORIES,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    college_company = forms.ChoiceField(
        choices=[("", "— Select —")] + COLLEGE_COMPANIES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = PendingUser
        fields = ["first_name", "last_name", "email", "category", "college_company"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class FLCRegistrationForm(forms.ModelForm):
    """Advisor adds participants (all dropdowns wired to your fixed choices)."""
    student_organization = forms.ChoiceField(
        choices=[("", "— Select —")] + STUDENT_ORGS, required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    college_company = forms.ChoiceField(
        choices=[("", "— Select —")] + COLLEGE_COMPANIES, required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    tour = forms.ChoiceField(
        choices=[("", "— Select —")] + TOURS, required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    tee_shirt_size = forms.ChoiceField(
        choices=[("", "— Select —")] + TEE_SIZES, required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    # Display-only fee field (not saved to DB)
    fee_display = forms.DecimalField(
        initial="40.00",
        max_digits=6,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Fee per participant ($)",
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = FLCRegistration
        fields = [
            "first_name", "last_name",
            "student_organization", "college_company",
            "tour", "tee_shirt_size",
            "food_allergy", "ada_needs",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "food_allergy": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional"}),
            "ada_needs": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional"}),
        }


class EventRegistrationForm(forms.Form):
    """Optional simple selector used by some legacy views."""
    user = forms.ModelChoiceField(
        queryset=PendingUser.objects.all(),
        required=True,
        label="Select Approved User",
        widget=forms.Select(attrs={"class": "form-select"})
    )


class NewUserRequestForm(forms.Form):
    """Your internal contact form (not the public Request Access form)."""
    first_name = forms.CharField(
        max_length=120, label="First Name",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        max_length=120, label="Last Name",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    category = forms.ChoiceField(
        choices=[("", "— Select —")] + CATEGORIES, label="Category",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    phone = forms.CharField(
        max_length=20, label="Phone (optional)", required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        label="Message (optional)", required=False
    )


class RequestAccessForm(forms.Form):
    """Public, non-DB Request Access form (with hCaptcha in the template)."""
    first_name = forms.CharField(
        max_length=120, label="First Name",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name  = forms.CharField(
        max_length=120, label="Last Name",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    student_organization = forms.ChoiceField(
        choices=[("", "— Select —")] + STUDENT_ORGS, label="Student Organization",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    college_company = forms.ChoiceField(
        choices=[("", "— Select —")] + COLLEGE_COMPANIES, label="College/Company",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    phone = forms.CharField(
        max_length=20, label="Cell (optional)", required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        label="Message (optional)", required=False
    )


class AccessRequestForm(forms.Form):
    """Tiny form used on /registrations/access/ to email a magic link."""
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "aria-label": "Email address",
            "autocomplete": "email",
            "required": "required"
        })
    )
