from django.urls import path

from . import views

app_name = "ai_assistant"

urlpatterns = [
    path("ask/", views.ask, name="ask"),
    path("history/", views.history, name="history"),
    path("history/<int:pk>/", views.history_detail, name="history_detail"),
    path("api/ask/", views.api_ask, name="api_ask"),
    path("api/usage/", views.api_usage, name="api_usage"),
]
