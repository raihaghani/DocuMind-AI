from django import forms
from django.conf import settings


class DocumentUploadForm(forms.Form):
    """Minimal upload form. Deep validation lives in services.validate_upload."""

    file = forms.FileField(
        label="Select a PDF or TXT file",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf,.txt",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = ", ".join(
            e.upper() for e in settings.ALLOWED_UPLOAD_EXTENSIONS
        )
        self.fields["file"].help_text = (
            f"Accepted: {allowed}. Maximum size: "
            f"{settings.MAX_UPLOAD_SIZE_MB} MB."
        )
