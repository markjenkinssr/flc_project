from django.http import HttpResponse, JsonResponse

def sanity_view(request):
    return HttpResponse("<h1>✅ Minimal sanity works</h1>", content_type="text/html")

def user_access_view(request):
    return HttpResponse("<h2>Access page placeholder</h2>", content_type="text/html")

def registration_form_view(request, user_id: int):
    return HttpResponse(f"<h2>Registration form for user_id={user_id}</h2>", content_type="text/html")

def finish_session_view(request, user_id: int):
    return HttpResponse(f"<h2>Finish session for user_id={user_id}</h2>", content_type="text/html")

def manage_pending_users(request):
    return HttpResponse("<h2>Manage Pending Users placeholder</h2>", content_type="text/html")

def get_names_by_category(request):
    return JsonResponse({"names": []})
