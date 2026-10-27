import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from documents.models import Document
from documents.services import process_upload
from documents.tests import pdf_upload, txt_upload
from workspace.models import get_or_create_workspace

from .models import AIRequest, UsageRecord
from .services.ai_provider import (
    MockProvider,
    ProviderError,
    ProviderTimeout,
    get_provider,
)
from .services.chunking import build_chunks
from .services.extraction import ExtractionResult, ExtractedSegment
from .services.retrieval import retrieve
from .services.usage import get_usage_summary, try_consume

TEMP_STORAGE = tempfile.mkdtemp(prefix="documind-ai-test-")


@override_settings(PRIVATE_STORAGE_ROOT=TEMP_STORAGE)
class ChunkingTests(TestCase):
    def test_short_text_is_single_chunk(self):
        result = ExtractionResult(segments=[ExtractedSegment("Hello world.", 1)])
        chunks = build_chunks(result, chunk_size=1000, overlap=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page_number, 1)

    def test_long_text_is_split_with_overlap(self):
        text = " ".join(f"sentence{i}" for i in range(400))
        result = ExtractionResult(segments=[ExtractedSegment(text, 1)])
        chunks = build_chunks(result, chunk_size=500, overlap=100)
        self.assertGreater(len(chunks), 1)
        # Sequence numbers are contiguous.
        self.assertEqual([c.seq for c in chunks], list(range(len(chunks))))


@override_settings(PRIVATE_STORAGE_ROOT=TEMP_STORAGE)
class RetrievalTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_STORAGE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("ret", "r@x.com", "Str0ngPass!23")
        self.doc = process_upload(
            self.user,
            get_or_create_workspace(self.user),
            txt_upload(
                "leave.txt",
                "Employees receive 20 days of annual paid leave each year. "
                "The office is closed on public holidays. "
                "Sick leave requires a medical certificate after three days.",
            ),
        )

    def test_relevant_chunk_retrieved(self):
        results = retrieve(self.doc.chunks.all(), "How many paid leave days?")
        self.assertTrue(results)
        self.assertIn("leave", results[0].text.lower())

    def test_empty_question_returns_nothing(self):
        self.assertEqual(retrieve(self.doc.chunks.all(), "  "), [])

    def test_no_chunks_returns_nothing(self):
        self.assertEqual(retrieve([], "anything"), [])

    def test_unrelated_question_filtered_by_threshold(self):
        results = retrieve(
            self.doc.chunks.all(), "quantum entanglement photon spin"
        )
        self.assertEqual(results, [])


@override_settings(PRIVATE_STORAGE_ROOT=TEMP_STORAGE, AI_PROVIDER="mock")
class MockProviderTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_STORAGE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("mp", "m@x.com", "Str0ngPass!23")
        self.doc = process_upload(
            self.user,
            get_or_create_workspace(self.user),
            txt_upload("faq.txt", "The warranty covers defects for 24 months."),
        )

    def test_mock_provider_is_default(self):
        self.assertIsInstance(get_provider(), MockProvider)

    def test_mock_returns_grounded_extractive_answer(self):
        retrieved = retrieve(self.doc.chunks.all(), "warranty length")
        answer = get_provider().generate(
            "warranty length", retrieved, self.doc.original_filename
        )
        self.assertTrue(answer.supported)
        self.assertTrue(answer.is_mock)
        self.assertIn("warranty", answer.answer.lower())
        self.assertTrue(answer.sources)

    def test_mock_abstains_when_no_evidence(self):
        answer = get_provider().generate("unrelated", [], "faq.txt")
        self.assertFalse(answer.supported)
        self.assertIn("couldn't find", answer.answer.lower())


class OpenAIProviderTests(TestCase):
    @override_settings(AI_PROVIDER="openai", AI_API_KEY="")
    def test_missing_credentials_raises(self):
        from .services.ai_provider import OpenAIProvider

        class FakeChunk:
            text = "data"
            page_number = 1
            reference = "Page 1"
            source_label = "Page 1"
            score = 0.5

        with self.assertRaises(ProviderError):
            OpenAIProvider().generate("q", [FakeChunk()], "d.pdf")

    @override_settings(AI_PROVIDER="openai", AI_API_KEY="key")
    def test_abstain_token_marks_unsupported(self):
        from .services.ai_provider import ABSTAIN_TOKEN, OpenAIProvider

        provider = OpenAIProvider()

        class FakeChunk:
            text = "irrelevant"
            page_number = 1
            reference = "Page 1"
            source_label = "Page 1"
            score = 0.3

        with mock.patch.object(
            provider, "_call_api", return_value=ABSTAIN_TOKEN
        ):
            answer = provider.generate("q", [FakeChunk()], "d.pdf")
        self.assertFalse(answer.supported)


@override_settings(PRIVATE_STORAGE_ROOT=TEMP_STORAGE, DAILY_QUESTION_LIMIT=3)
class UsageTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_STORAGE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.a = User.objects.create_user("ua", "a@x.com", "Str0ngPass!23")
        self.b = User.objects.create_user("ub", "b@x.com", "Str0ngPass!23")

    def test_quota_starts_full(self):
        summary = get_usage_summary(self.a)
        self.assertEqual(summary["used"], 0)
        self.assertEqual(summary["remaining"], 3)

    def test_consumption_counts_and_limits(self):
        self.assertTrue(try_consume(self.a))
        self.assertTrue(try_consume(self.a))
        self.assertTrue(try_consume(self.a))
        # Fourth attempt is over the limit.
        self.assertFalse(try_consume(self.a))
        self.assertEqual(get_usage_summary(self.a)["used"], 3)

    def test_users_have_separate_quotas(self):
        try_consume(self.a)
        try_consume(self.a)
        self.assertEqual(get_usage_summary(self.a)["used"], 2)
        self.assertEqual(get_usage_summary(self.b)["used"], 0)

    def test_daily_reset_via_new_date_record(self):
        # Simulate yesterday's exhausted quota; today should be fresh.
        yesterday = timezone.localdate() - timezone.timedelta(days=1)
        UsageRecord.objects.create(user=self.a, date=yesterday, count=3)
        self.assertEqual(get_usage_summary(self.a)["remaining"], 3)


@override_settings(PRIVATE_STORAGE_ROOT=TEMP_STORAGE, DAILY_QUESTION_LIMIT=3,
                   AI_PROVIDER="mock")
class AskApiTests(TestCase):
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
            txt_upload(
                "policy.txt",
                "Employees receive 20 days of annual paid leave every year.",
            ),
        )

    def _ask(self, document_id, question):
        return self.client.post(
            reverse("ai_assistant:api_ask"),
            data=json.dumps({"document_id": document_id, "question": question}),
            content_type="application/json",
        )

    def test_unauthenticated_gets_401(self):
        response = self._ask(self.alice_doc.pk, "How much leave?")
        self.assertEqual(response.status_code, 401)

    def test_successful_question_saves_history_and_counts_usage(self):
        self.client.force_login(self.alice)
        response = self._ask(self.alice_doc.pk, "How many paid leave days?")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["sources"])
        self.assertEqual(data["usage"]["used"], 1)
        req = AIRequest.objects.get(user=self.alice)
        self.assertEqual(req.status, AIRequest.Status.SUCCESS)

    def test_empty_question_rejected_and_not_charged(self):
        self.client.force_login(self.alice)
        response = self._ask(self.alice_doc.pk, "   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(get_usage_summary(self.alice)["used"], 0)

    def test_unsupported_question_saved_as_unsupported(self):
        self.client.force_login(self.alice)
        response = self._ask(self.alice_doc.pk, "zxcvbnm asdfghjkl qwerty")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unsupported")
        req = AIRequest.objects.get(user=self.alice)
        self.assertEqual(req.status, AIRequest.Status.UNSUPPORTED)

    def test_cannot_query_another_users_document(self):
        self.client.force_login(self.bob)
        response = self._ask(self.alice_doc.pk, "How much leave?")
        self.assertEqual(response.status_code, 404)
        # Bob was not charged for an unauthorized request.
        self.assertEqual(get_usage_summary(self.bob)["used"], 0)

    def test_quota_enforced_via_api(self):
        self.client.force_login(self.alice)
        for _ in range(3):
            self.assertEqual(
                self._ask(self.alice_doc.pk, "leave days?").status_code, 200
            )
        over = self._ask(self.alice_doc.pk, "leave days?")
        self.assertEqual(over.status_code, 429)
        self.assertEqual(get_usage_summary(self.alice)["used"], 3)

    def test_provider_timeout_returns_503_and_saves_failed(self):
        self.client.force_login(self.alice)

        class Boom(MockProvider):
            def generate(self, *a, **k):
                raise ProviderTimeout("timeout")

        with mock.patch("ai_assistant.views.get_provider", return_value=Boom()):
            response = self._ask(self.alice_doc.pk, "How much leave?")
        self.assertEqual(response.status_code, 503)
        self.assertTrue(
            AIRequest.objects.filter(
                user=self.alice, status=AIRequest.Status.FAILED
            ).exists()
        )

    def test_history_is_private(self):
        self.client.force_login(self.alice)
        self._ask(self.alice_doc.pk, "How many paid leave days?")
        req = AIRequest.objects.get(user=self.alice)

        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("ai_assistant:history_detail", args=[req.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_history_retained_after_document_deleted(self):
        self.client.force_login(self.alice)
        self._ask(self.alice_doc.pk, "How many paid leave days?")
        from documents.services import delete_document

        delete_document(self.alice_doc)
        req = AIRequest.objects.get(user=self.alice)
        self.assertIsNone(req.document)
        self.assertEqual(req.document_name, "policy.txt")
