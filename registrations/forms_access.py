from __future__ import annotations
from django import forms

# Choices (adjust labels as you like)
TEE_CHOICES = [
    ("XS", "XS"), ("S", "S"), ("M", "M"), ("L", "L"),
    ("XL", "XL"), ("2XL", "2XL"), ("3XL", "3XL"),
]
TOUR_CHOICES = [
    ("Tour A", "Tour A"),
    ("Tour B", "Tour B"),
    ("Tour C", "Tour C"),
]

def _aria(attrs: dict[str, str] | None = None, required: bool = False) -> dict[str, str]:
    base = {
        "class": "form-control",
        "aria-required": "true" if required else "false",
    }
    if attrs:
        base.update(attrs)
    return base

class RegistrationForm(forms.Form):
    first_name         = forms.CharField(max_length=100, required=True,
                            widget=forms.TextInput(attrs=_aria({"autocomplete":"given-name"}, True)))
    last_name          = forms.CharField(max_length=100, required=True,
                            widget=forms.TextInput(attrs=_aria({"autocomplete":"family-name"}, True)))
    student_organization = forms.CharField(max_length=200, required=False,
                            widget=forms.TextInput(attrs=_aria({"placeholder":"e.g., STEM Club"})))
    college_company    = forms.CharField(max_length=200, required=False,
                            widget=forms.TextInput(attrs=_aria({"placeholder":"e.g., MCCB or Sponsor"})))
    tour               = forms.ChoiceField(choices=TOUR_CHOICES, required=False,
                            widget=forms.Select(attrs=_aria()))
    tee_shirt_size     = forms.ChoiceField(choices=TEE_CHOICES, required=False,
                            widget=forms.Select(attrs=_aria()))
    food_allergy       = forms.CharField(max_length=200, required=False,
                            widget=forms.TextInput(attrs=_aria({"placeholder":"Peanut, Shellfish, None"})))
    ada_needs          = forms.CharField(max_length=300, required=False,
                            widget=forms.TextInput(attrs=_aria({"placeholder":"Wheelchair access, ASL, etc."})))
