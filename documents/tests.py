import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from workspace.models import get_or_create_workspace

from .models import Document, DocumentChunk
from .services import UploadValidationError, process_upload

TEMP_STORAGE = tempfile.mkdtemp(prefix="documind-test-")


def make_pdf_bytes(pages_text):
    """Build a tiny real PDF (one page per string) using PyMuPDF."""
    import fitz

    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def pdf_upload(name, pages_text):
    return SimpleUploadedFile(
        name, make_pdf_bytes(pages_text), content_type="application/pdf"
    )


def txt_upload(name, text):
    return SimpleUploadedFile(
        name, text.encode("utf-8"), content_type="text/plain"
    )


@override_settings(PRIVATE_STORAGE_ROOT=TEMP_STORAGE)
class DocumentProcessingTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_STORAGE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("owner", "o@x.com", "Str0ngPass!23")
        self.workspace = get_or_create_workspace(self.user)

    def test_valid_pdf_upload_creates_ready_document_with_chunks(self):
        doc = process_upload(
            self.user,
            self.workspace,
            pdf_upload("policy.pdf", ["Employees receive 20 days of paid leave."]),
        )
        self.assertEqual(doc.status, Document.Status.READY)
        self.assertGreater(doc.chunk_count, 0)
        self.assertEqual(doc.page_count, 1)
        self.assertEqual(doc.chunks.first().page_number, 1)

    def test_valid_txt_upload(self):
        doc = process_upload(
            self.user,
            self.workspace,
            txt_upload("notes.txt", "The warranty period is two years.\n" * 5),
        )
        self.assertEqual(doc.status, Document.Status.READY)
        self.assertGreater(doc.chunk_count, 0)

    def test_invalid_file_type_rejected(self):
        with self.assertRaises(UploadValidationError):
            process_upload(
                self.user,
                self.workspace,
                SimpleUploadedFile("bad.docx", b"x", content_type="application/x"),
            )

    def test_empty_file_rejected(self):
        with self.assertRaises(UploadValidationError):
            process_upload(
                self.user,
                self.workspace,
                SimpleUploadedFile("empty.txt", b"", content_type="text/plain"),
            )

    @override_settings(MAX_UPLOAD_SIZE_BYTES=10)
    def test_oversized_file_rejected(self):
        with self.assertRaises(UploadValidationError):
            process_upload(
                self.user,
                self.workspace,
                txt_upload("big.txt", "x" * 100),
            )

    def test_corrupted_pdf_marked_failed(self):
        doc = process_upload(
            self.user,
            self.workspace,
            SimpleUploadedFile(
                "corrupt.pdf", b"%PDF-1.4 not really a pdf",
                content_type="application/pdf",
            ),
        )
        self.assertEqual(doc.status, Document.Status.FAILED)
        self.assertEqual(doc.chunk_count, 0)

    def test_pdf_without_text_marked_failed(self):
        # A valid but text-less PDF (blank page) simulates a scanned document.
        doc = process_upload(
            self.user, self.workspace, pdf_upload("scan.pdf", [""])
        )
        self.assertEqual(doc.status, Document.Status.FAILED)
        self.assertIn("text", doc.error_message.lower())


@override_settings(PRIVATE_STORAGE_ROOT=TEMP_STORAGE)
class DocumentAuthorizationTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_STORAGE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.alice = User.objects.create_user("alice", "a@x.com", "Str0ngPass!23")
        self.bob = User.objects.create_user("bob", "b@x.com", "Str0ngPass!23")
        self.alice_doc = process_upload(
            self.alice,
            get_or_create_workspace(self.alice),
            txt_upload("alice.txt", "Alice secret content about budgets."),
        )

    def test_user_cannot_view_others_document_detail(self):
        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("documents:detail", args=[self.alice_doc.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_download_others_document(self):
        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("documents:download", args=[self.alice_doc.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_others_document(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("documents:delete", args=[self.alice_doc.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Document.objects.filter(pk=self.alice_doc.pk).exists())

    def test_owner_can_download(self):
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse("documents:download", args=[self.alice_doc.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_owner_can_delete_and_file_removed(self):
        abs_path = self.alice_doc.absolute_path
        self.assertTrue(abs_path.exists())
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("documents:delete", args=[self.alice_doc.pk])
        )
        self.assertRedirects(response, reverse("documents:list"))
        self.assertFalse(Document.objects.filter(pk=self.alice_doc.pk).exists())
        self.assertFalse(
            DocumentChunk.objects.filter(document_id=self.alice_doc.pk).exists()
        )
        self.assertFalse(abs_path.exists())
