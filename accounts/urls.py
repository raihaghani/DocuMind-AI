from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.DocuMindLoginView.as_view(), name="login"),
    path("logout/", views.DocuMindLogoutView.as_view(), name="logout"),
    path("account/", views.account, name="account"),
]
