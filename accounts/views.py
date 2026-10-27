from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from .forms import RegistrationForm


@require_http_methods(["GET", "POST"])
def register(request):
    """Register a new account and log the user in on success."""
    if request.user.is_authenticated:
        return redirect("workspace:dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request, "Welcome to DocuMind AI! Your workspace is ready."
            )
            return redirect("workspace:dashboard")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class DocuMindLoginView(LoginView):
    """Session-based login; bounces authenticated users to the dashboard."""

    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    authentication_form = AuthenticationForm

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password.")
        return super().form_invalid(form)


class DocuMindLogoutView(LogoutView):
    """POST-only logout (Django 5 enforces POST by default)."""

    next_page = reverse_lazy("accounts:login")


@login_required
def account(request):
    """Simple account overview page."""
    return render(request, "accounts/account.html")
