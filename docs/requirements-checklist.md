# Requirements Traceability Checklist

Maps each functional requirement to its implementation and automated test
coverage. "Complete" is only used where the feature is implemented **and**
verified by a passing test or by the documented manual check.

| Requirement | Implementation | Test Coverage | Status |
| ----------- | -------------- | ------------- | ------ |
| User registration | `accounts/forms.py` `RegistrationForm`, `accounts/views.register` | `accounts/tests.py::test_registration_*` | Complete |
| Login (session) | `accounts/views.DocuMindLoginView` | `accounts/tests.py::test_login_and_logout`, `test_invalid_login_shows_error` | Complete |
| Logout (POST-only) | `accounts/views.DocuMindLogoutView` | `accounts/tests.py::test_login_and_logout` | Complete |
| Protected private pages | `@login_required` on all private views; `401` on JSON API | `accounts/tests.py::test_protected_pages_require_login`; `ai_assistant/tests.py::test_unauthenticated_gets_401` | Complete |
| Private per-user workspace | `workspace/models.Workspace` (OneToOne), signal auto-create | `workspace/tests.py::WorkspaceModelTests` | Complete |
| Dashboard with live stats | `workspace/views.dashboard` + `templates/workspace/dashboard.html` | `workspace/tests.py::test_dashboard_shows_live_document_count` | Complete |
| Document upload (PDF/TXT) | `documents/services.process_upload`, `documents/views.document_upload` | `documents/tests.py::test_valid_pdf_upload_*`, `test_valid_txt_upload` | Complete |
| Upload validation (type/size/empty/corrupt/no-text) | `documents/services.validate_upload` + extraction | `documents/tests.py::test_invalid_file_type_rejected`, `test_empty_file_rejected`, `test_oversized_file_rejected`, `test_corrupted_pdf_marked_failed`, `test_pdf_without_text_marked_failed` | Complete |
| Private storage + safe filenames | `documents/services._save_file` (UUID names, per-user dir) | Exercised by upload/download tests | Complete |
| Secure, ownership-checked download | `documents/views.document_download` (+ path-traversal guard) | `documents/tests.py::test_owner_can_download`, `test_user_cannot_download_others_document` | Complete |
| Document delete (file + chunks) | `documents/services.delete_document`, `documents/views.document_delete` | `documents/tests.py::test_owner_can_delete_and_file_removed`, `test_user_cannot_delete_others_document` | Complete |
| Text extraction (PyMuPDF/stdlib, page refs) | `ai_assistant/services/extraction.py` | `documents/tests.py` (PDF page_number), extraction edge cases | Complete |
| Text chunking (overlap, refs) | `ai_assistant/services/chunking.py` | `ai_assistant/tests.py::ChunkingTests` | Complete |
| TF-IDF retrieval (cosine, top-K, threshold) | `ai_assistant/services/retrieval.py` | `ai_assistant/tests.py::RetrievalTests` | Complete |
| Document isolation in retrieval | query scoped to owned document; denormalized `owner` | `ai_assistant/tests.py::test_cannot_query_another_users_document` | Complete |
| AI-assisted question answering | `ai_assistant/views.api_ask` + provider | `ai_assistant/tests.py::AskApiTests` | Complete |
| Grounded answers + source references | `ai_provider.py` `_build_sources`, sources in response/UI | `ai_assistant/tests.py::test_successful_question_saves_history_and_counts_usage` | Complete |
| Mock provider (honest, labelled) | `ai_assistant/services/ai_provider.MockProvider` | `ai_assistant/tests.py::MockProviderTests` | Complete |
| Real provider (configurable, grounding prompt) | `ai_assistant/services/ai_provider.OpenAIProvider` | `ai_assistant/tests.py::OpenAIProviderTests` (abstain + missing creds) | Complete |
| Unsupported-question handling | threshold → empty retrieval → abstain message | `ai_assistant/tests.py::test_unsupported_question_saved_as_unsupported`, `RetrievalTests::test_unrelated_question_filtered_by_threshold` | Complete |
| Provider failure/timeout handling (503) | `ProviderError`/`ProviderTimeout` → 503, saved as failed | `ai_assistant/tests.py::test_provider_timeout_returns_503_and_saves_failed` | Complete |
| Request history (persistent, statuses) | `ai_assistant/models.AIRequest`, history views | `ai_assistant/tests.py::AskApiTests` (success/unsupported/failed saved) | Complete |
| History private to user | ownership-scoped queries | `ai_assistant/tests.py::test_history_is_private` | Complete |
| History retained after doc deletion | `AIRequest.document` SET_NULL + `document_name` snapshot | `ai_assistant/tests.py::test_history_retained_after_document_deleted` | Complete |
| Daily usage limits (atomic) | `ai_assistant/services/usage.py` (`try_consume`, `select_for_update`) | `ai_assistant/tests.py::UsageTests`, `test_quota_enforced_via_api` | Complete |
| Usage accounting policy | charge on accept; not on invalid/unauth/over-limit | `ai_assistant/tests.py::test_empty_question_rejected_and_not_charged`, `test_cannot_query_another_users_document` (not charged) | Complete |
| Limit cannot be bypassed via API | server-side enforcement in `api_ask` | `ai_assistant/tests.py::test_quota_enforced_via_api` | Complete |
| CSRF protection | enabled globally; `X-CSRFToken` in `ask.js` | Django test client enforces CSRF middleware config | Complete |
| User isolation (cross-user access blocked) | ownership in queries → 404 | `documents/tests.py::DocumentAuthorizationTests`, `ai_assistant/tests.py` | Complete |
| Error handling (no tracebacks, status codes) | friendly messages + 400/401/404/429/503 | `ai_assistant/tests.py::AskApiTests` | Complete |
| Prompt-injection defense | provider system prompt treats docs as untrusted data | Documented in `docs/security.md`; prompt in `ai_provider.py` | Complete |
| Documentation | `README.md` + `docs/*` | n/a | Complete |
| Architecture diagram | `docs/architecture-diagram.md` (Mermaid + Lucidchart spec) | n/a | Complete |
| ERD | `docs/database-erd.md` | n/a | Complete |
| API documentation | `docs/api-documentation.md` | n/a | Complete |
| API flow diagram | `docs/api-flow.md` | n/a | Complete |
| Cost & scaling analysis | `docs/cost-and-scaling-analysis.md` | n/a | Complete |
| Concurrency protection (quota) | `select_for_update` atomic consume | Logic covered by `UsageTests`; true row-locking requires PostgreSQL (documented) | Partially complete |

## Notes

- **Concurrency** is implemented via `select_for_update()`. On SQLite (dev) the
  database serializes writes; strict row-level locking under heavy concurrency
  requires PostgreSQL. This limitation is documented in
  `docs/architecture.md` and the README, hence "Partially complete".
- OCR for scanned PDFs is intentionally **not implemented** (out of MVP scope);
  such files are rejected with a clear message.
