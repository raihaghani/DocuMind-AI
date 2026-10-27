from django.urls import path

from . import views

app_name = "workspace"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
]
