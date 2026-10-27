from django.contrib import admin

from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "original_filename",
        "owner",
        "file_type",
        "status",
        "chunk_count",
        "uploaded_at",
    )
    list_filter = ("status", "file_type")
    search_fields = ("original_filename", "owner__username")
    readonly_fields = ("uploaded_at",)


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "seq", "page_number", "owner")
    search_fields = ("document__original_filename",)
