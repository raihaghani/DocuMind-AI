import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from documents.services import process_upload
from documents.tests import txt_upload

from .models import Workspace, get_or_create_workspace

TEMP_STORAGE = tempfile.mkdtemp(prefix="documind-ws-test-")


class WorkspaceModelTests(TestCase):
    def test_workspace_created_on_user_creation(self):
        user = User.objects.create_user("wsuser", "w@x.com", "Str0ngPass!23")
        self.assertTrue(Workspace.objects.filter(owner=user).exists())

    def test_get_or_create_is_idempotent(self):
        user = User.objects.create_user("wsuser2", "w2@x.com", "Str0ngPass!23")
        ws1 = get_or_create_workspace(user)
        ws2 = get_or_create_workspace(user)
        self.assertEqual(ws1.pk, ws2.pk)


@override_settings(PRIVATE_STORAGE_ROOT=TEMP_STORAGE)
class DashboardTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_STORAGE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("dash", "d@x.com", "Str0ngPass!23")

    def test_dashboard_shows_live_document_count(self):
        process_upload(
            self.user,
            get_or_create_workspace(self.user),
            txt_upload("a.txt", "Some content for the dashboard count test."),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("workspace:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_documents"], 1)
        self.assertEqual(response.context["questions_used_today"], 0)
