from django.urls import path
from . import views_full as vr  # <- real views

app_name = "registrations"

urlpatterns = [
    path("sanity/", vr.sanity_view, name="sanity"),
    path("user-access/", vr.user_access_view, name="user_access"),
    path("form/<int:user_id>/", vr.registration_form_view, name="registration_form"),
    path("finish/<int:user_id>/", vr.finish_session_view, name="finish_session"),
    path("manage-pending-users/", vr.manage_pending_users, name="manage_pending_users"),
    path("ajax/names/", vr.get_names_by_category, name="ajax_names"),
]
