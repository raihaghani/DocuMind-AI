from django.apps import AppConfig


class WorkspaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workspace"

    def ready(self):
        # Register signal handlers (auto-create a workspace per new user).
        from . import signals  # noqa: F401
