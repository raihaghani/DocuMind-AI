from django.contrib import admin

from .models import AIRequest, UsageRecord


@admin.register(AIRequest)
class AIRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "document_name",
        "status",
        "provider_mode",
        "created_at",
    )
    list_filter = ("status", "provider_mode")
    search_fields = ("question", "user__username", "document_name")
    readonly_fields = ("created_at",)


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "count")
    list_filter = ("date",)
    search_fields = ("user__username",)
