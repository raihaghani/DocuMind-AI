from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ai_assistant.models import AIRequest
from ai_assistant.services.usage import get_usage_summary
from documents.models import Document

from .models import get_or_create_workspace


def landing(request):
    """Public landing page. Authenticated users go straight to the dashboard."""
    if request.user.is_authenticated:
        return redirect("workspace:dashboard")
    return render(request, "workspace/landing.html")


@login_required
def dashboard(request):
    """Private workspace dashboard with live, database-derived statistics."""
    workspace = get_or_create_workspace(request.user)

    documents = Document.objects.filter(owner=request.user)
    requests_qs = AIRequest.objects.filter(user=request.user)

    usage = get_usage_summary(request.user)

    context = {
        "workspace": workspace,
        "total_documents": documents.count(),
        "total_questions": requests_qs.count(),
        "questions_used_today": usage["used"],
        "daily_limit": usage["limit"],
        "remaining_today": usage["remaining"],
        "usage_percent": usage["percent"],
        "recent_documents": documents.order_by("-uploaded_at")[:5],
        "recent_requests": requests_qs.order_by("-created_at")[:5],
    }
    return render(request, "workspace/dashboard.html", context)
