from django.urls import path
from . import views_flat as views

urlpatterns = [
    path("sanity/", views.sanity_view, name="registrations_sanity"),
    path("form/", views.form_view, name="registrations_form"),
    path("manage-pending-users/", views.manage_pending_users_view, name="registrations_manage_pending_users"),
]
