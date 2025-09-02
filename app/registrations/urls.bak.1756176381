# registrations/urls.py
from django.urls import path
from . import views

app_name = "registrations"

urlpatterns = [
    # ---- sanity / home ----
    path("sanity/", views.sanity_view, name="sanity"),
    path("", views.registration_home_view, name="registration_home"),

    # ---- advisor access (primary + legacy alias) ----
    path("user-access/", views.user_access_view, name="user_access"),                 # primary
    path("access/", views.user_access_view, name="user_access_legacy"),               # legacy alias

    # ---- ajax helpers ----
    path("get-names-by-category/", views.get_names_by_category, name="get_names_by_category"),
    path("ajax/names/", views.get_names_by_category, name="ajax_names"),              # legacy alias
    path("ajax/update-user/<int:user_id>/", views.update_pending_user, name="ajax_update_user"),
    path("ajax/delete-user/<int:user_id>/", views.delete_pending_user, name="ajax_delete_user"),

    # ---- validation & resend ----
    path("validate/<str:token>/", views.validate_user, name="validate_user"),
    path("resend-validation/<int:user_id>/", views.resend_validation, name="resend_validation"),
    path("resend/<int:user_id>/", views.resend_validation, name="resend_validation_legacy"),  # legacy alias

    # ---- registration form (primary + legacy aliases) ----
    path("registration/<int:user_id>/", views.registration_form_view, name="registration_form"),   # primary
    path("form/<int:user_id>/", views.registration_form_view, name="registration_form_legacy"),     # legacy alias
    path("form/", views.registration_form_view, name="registration_form_no_id"),

    # ---- finish session (primary + legacy alias) ----
    path("finish/<int:user_id>/", views.finish_session_view, name="finish_session"),               # primary
    path("session/<int:user_id>/finish/", views.finish_session_view, name="finish_session_legacy"),

    # ---- request access (public) ----
    path("request-access/", views.request_access_view, name="request_access"),
    path("request-access/success/", views.request_access_success_view, name="request_access_success"),

    # ---- new user request (internal contact form) ----
    path("new-user-request/", views.new_user_request_view, name="new_user_request"),

    # ---- event registration (optional) ----
    path("event/", views.event_registration_view, name="event_registration"),

    # ---- success / confirmation screens ----
    path("confirmation/", views.registration_success_view, name="registration_success"),
    path("request-confirmation/", views.request_success_view, name="request_success"),
    path("confirmation-sent/<str:email>/", views.confirmation_sent, name="confirmation_sent"),
    path("confirmation-sent/resend/", views.resend_confirmation, name="resend_confirmation"),

    # ---- manage pending users ----
    path("manage-pending-users/", views.manage_pending_users, name="manage_pending_users"),
    path("quick-add/", views.quick_add_pending_user, name="quick_add_pending_user"),

    # ---- reports (csv download + email) ----
    path("reports/all.csv", views.download_all_registrations_csv, name="download_all_csv"),
    path("reports/email-all", views.email_all_registrations_csv, name="email_all_csv"),

    # ---- forms dashboard ----
    path("forms/", views.forms_dashboard, name="forms_dashboard"),

    # registrations/urls.py (additions)
    path(
    "registration/<int:user_id>/edit/<int:reg_id>/",
    views.registration_edit_view,
    name="registration_edit",
    ),
    path(
    "registration/<int:user_id>/delete/<int:reg_id>/",
    views.registration_delete_view,
    name="registration_delete",
),

    
]
