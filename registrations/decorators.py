# registrations/decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from .constants import ACCESS_SESSION_KEY

def require_access(viewfunc):
    def _wrapped(request, *args, **kwargs):
        if not request.session.get(ACCESS_SESSION_KEY):
            messages.error(request, "Please request access first.")
            return redirect("registrations:user_access")  # or "registrations:access_request"
        return viewfunc(request, *args, **kwargs)
    return _wrapped
