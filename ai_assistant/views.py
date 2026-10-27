import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from documents.models import Document

from .models import AIRequest
from .services.ai_provider import ProviderError, ProviderTimeout, get_provider
from .services.retrieval import retrieve
from .services.usage import get_usage_summary, try_consume

logger = logging.getLogger("documind")


# ---------------------------------------------------------------------------
# Page views
# ---------------------------------------------------------------------------
@login_required
def ask(request):
    documents = Document.objects.filter(
        owner=request.user, status=Document.Status.READY
    ).order_by("-uploaded_at")
    context = {
        "documents": documents,
        "usage": get_usage_summary(request.user),
        "has_documents": documents.exists(),
    }
    return render(request, "ai_assistant/ask.html", context)


@login_required
def history(request):
    requests_qs = AIRequest.objects.filter(user=request.user)
    paginator = Paginator(requests_qs, 10)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "ai_assistant/history.html", {"page_obj": page})


@login_required
def history_detail(request, pk):
    ai_request = get_object_or_404(AIRequest, pk=pk, user=request.user)
    return render(
        request, "ai_assistant/history_detail.html", {"ai_request": ai_request}
    )


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------
def _json_error(message, status):
    return JsonResponse({"error": message, "status": status}, status=status)


def _require_auth_json(request):
    if not request.user.is_authenticated:
        return _json_error("Authentication required.", 401)
    return None


@require_POST
def api_ask(request):
    """Submit a question about an owned, processed document.

    Quota is consumed only once the request is accepted for processing
    (valid input, owned & ready document, quota available). See
    services/usage.py for the full policy.
    """
    auth_error = _require_auth_json(request)
    if auth_error:
        return auth_error

    # Accept both form-encoded and JSON bodies.
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return _json_error("Invalid JSON body.", 400)
        document_id = payload.get("document_id")
        question = payload.get("question", "")
    else:
        document_id = request.POST.get("document_id")
        question = request.POST.get("question", "")

    question = (question or "").strip()
    if not question:
        return _json_error("Please enter a question.", 400)

    from django.conf import settings

    if len(question) > settings.MAX_QUESTION_LENGTH:
        return _json_error(
            f"Question is too long (max {settings.MAX_QUESTION_LENGTH} "
            "characters).",
            400,
        )

    if not document_id:
        return _json_error("Please select a document.", 400)

    # Ownership enforced in the query (404 hides others' documents).
    try:
        document = Document.objects.get(pk=document_id, owner=request.user)
    except (Document.DoesNotExist, ValueError, TypeError):
        return _json_error("Document not found.", 404)

    if document.status != Document.Status.READY:
        return _json_error(
            "This document is not ready for questions yet.", 400
        )

    # Quota check + atomic consumption. Rejected (429) requests do NOT consume.
    if not try_consume(request.user):
        return _json_error(
            "Daily question limit reached. Please try again tomorrow.", 429
        )

    # Retrieval is scoped to this user's authorized document chunks only.
    chunks = document.chunks.all()
    retrieved = retrieve(chunks, question)

    provider = get_provider()
    try:
        result = provider.generate(question, retrieved, document.original_filename)
    except ProviderTimeout:
        ai_request = _save_request(
            request.user, document, question, "", AIRequest.Status.FAILED,
            provider.name, [], "AI service timed out.",
        )
        return _json_error("The AI service timed out. Please try again.", 503)
    except ProviderError as exc:
        _save_request(
            request.user, document, question, "", AIRequest.Status.FAILED,
            provider.name, [], str(exc),
        )
        return _json_error(
            "The AI service is currently unavailable. Please try again later.",
            503,
        )

    status = (
        AIRequest.Status.SUCCESS if result.supported
        else AIRequest.Status.UNSUPPORTED
    )
    ai_request = _save_request(
        request.user, document, question, result.answer, status,
        result.provider, result.sources, "",
    )

    usage = get_usage_summary(request.user)
    return JsonResponse(
        {
            "id": ai_request.id,
            "status": status,
            "answer": result.answer,
            "supported": result.supported,
            "is_mock": result.is_mock,
            "provider": result.provider,
            "sources": result.sources,
            "usage": usage,
        }
    )


def _save_request(user, document, question, answer, status, provider, sources, error):
    return AIRequest.objects.create(
        user=user,
        document=document,
        document_name=document.original_filename,
        question=question,
        answer=answer,
        status=status,
        provider_mode=provider,
        sources=sources,
        error_detail=error,
    )


@require_GET
def api_usage(request):
    auth_error = _require_auth_json(request)
    if auth_error:
        return auth_error
    return JsonResponse(get_usage_summary(request.user))
