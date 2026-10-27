import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from workspace.models import get_or_create_workspace

from .forms import DocumentUploadForm
from .models import Document
from .services import UploadValidationError, delete_document, process_upload


@login_required
def document_list(request):
    documents = Document.objects.filter(owner=request.user)
    return render(request, "documents/list.html", {"documents": documents})


@login_required
@require_http_methods(["GET", "POST"])
def document_upload(request):
    workspace = get_or_create_workspace(request.user)
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                document = process_upload(
                    request.user, workspace, form.cleaned_data["file"]
                )
            except UploadValidationError as exc:
                messages.error(request, str(exc))
            else:
                if document.status == Document.Status.READY:
                    messages.success(
                        request,
                        f"\"{document.original_filename}\" uploaded and "
                        f"processed ({document.chunk_count} chunks).",
                    )
                else:
                    messages.warning(
                        request,
                        f"\"{document.original_filename}\" was uploaded but "
                        f"could not be processed: {document.error_message}",
                    )
                return redirect("documents:detail", pk=document.pk)
    else:
        form = DocumentUploadForm()
    return render(request, "documents/upload.html", {"form": form})


@login_required
def document_detail(request, pk):
    # Ownership enforced in the query: others' documents return 404.
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    return render(request, "documents/detail.html", {"document": document})


@login_required
def document_download(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)

    abs_path = document.absolute_path
    # Defense in depth against path traversal: resolved path must stay inside
    # the private storage root.
    from django.conf import settings

    storage_root = os.path.realpath(settings.PRIVATE_STORAGE_ROOT)
    resolved = os.path.realpath(abs_path)
    if not resolved.startswith(storage_root + os.sep) or not os.path.exists(
        resolved
    ):
        raise Http404("File not found.")

    content_type = (
        "application/pdf" if document.file_type == "pdf" else "text/plain"
    )
    response = FileResponse(
        open(resolved, "rb"),
        as_attachment=True,
        filename=document.original_filename,
        content_type=content_type,
    )
    return response


@login_required
@require_POST
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user)
    name = document.original_filename
    delete_document(document)
    messages.success(request, f"\"{name}\" was deleted.")
    return redirect("documents:list")
