from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegistrationForm(UserCreationForm):
    """Registration form with username, email and a confirmed password.

    Builds on Django's UserCreationForm so that password strength is validated
    through the configured AUTH_PASSWORD_VALIDATORS and hashing is handled
    securely by Django.
    """

    email = forms.EmailField(
        required=True,
        help_text="A valid email address.",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bootstrap styling + friendlier widgets.
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autofocus": True}
        )
        self.fields["password1"].widget.attrs.update({"class": "form-control"})
        self.fields["password2"].widget.attrs.update({"class": "form-control"})

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with that email already exists."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
