# flc_project/urls.py

# flc_project/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("registrations/", include(("registrations.urls", "registrations"), namespace="registrations")),
]
