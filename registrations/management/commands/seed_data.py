from django.core.management.base import BaseCommand
from registrations.models import Category, PendingUser
import random

CATEGORIES = [
    "Coahoma Community College", "Copiah-Lincoln Community College", "Delta State University",
    "East Central Community College", "East Mississippi Community College",
    "Hinds Community College", "Holmes Community College",
    "Itawamba Community College", "Jones County",
    "Meridian Community College", "Mississippi Delta Community College",
    "Mississippi Gulf Coast Community College", "Northeast Mississippi Community College",
    "Northwest Mississippi Community College", "Pearl River Community College",
    "Southwest Mississippi Community College", "Mississippi Community College Board","Other",
]

USERS = [
    ("Mark", "Jenkins"), ("Danielle", "Clay"), ("Heidi", "Jenkins"), ("Kimberly", "Jones"),
    # ... continue until you have 65 names
]

class Command(BaseCommand):
    help = 'Seeds categories and pending users'

    def handle(self, *args, **kwargs):
        for cat in CATEGORIES:
            Category.objects.get_or_create(name=cat)

        all_categories = list(Category.objects.all())
        for i, (first, last) in enumerate(USERS):
            email = f"{first.lower()}.{last.lower()}@example.com"
            category = random.choice(all_categories)
            PendingUser.objects.get_or_create(
                first_name=first,
                last_name=last,
                email=email,
                category=category,
                verified=False
            )
        self.stdout.write(self.style.SUCCESS("Seeded categories and 65 users successfully"))
