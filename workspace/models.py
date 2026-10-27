from django.conf import settings
from django.db import models


class Workspace(models.Model):
    """A private, per-user workspace that owns documents and AI requests.

    The assignment calls for a simple, single-owner workspace (no team
    collaboration), so this is a one-to-one relationship with the user.
    """

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace",
    )
    name = models.CharField(max_length=120, default="My Workspace")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.owner})"


def get_or_create_workspace(user):
    """Return the user's workspace, creating it on first access."""
    workspace, _ = Workspace.objects.get_or_create(
        owner=user,
        defaults={"name": f"{user.username}'s Workspace"},
    )
    return workspace
