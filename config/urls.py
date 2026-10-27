"""Root URL configuration for DocuMind AI."""
from django.contrib import admin
from django.urls import include, path

from workspace import views as workspace_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", workspace_views.landing, name="landing"),
    path("", include("accounts.urls")),
    path("", include("workspace.urls")),
    path("documents/", include("documents.urls")),
    path("", include("ai_assistant.urls")),
]
