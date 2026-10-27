# Architecture

## 1. System architecture

DocuMind AI is a single Django project composed of four focused apps plus a
`services` layer that holds the document-processing and AI logic. It is a
classic server-rendered web application (Django Templates + Bootstrap) with one
small JSON API used for asynchronous question submission.

```
accounts     -> authentication (register / login / logout)
workspace    -> Workspace model + dashboard (live statistics)
documents    -> Document & DocumentChunk models; upload, storage, download,
                delete; documents/services.py orchestrates processing
ai_assistant -> AIRequest & UsageRecord models; ask page, history, JSON API;
                services/{extraction, chunking, retrieval, ai_provider, usage}
```

Keeping the heavy logic in `ai_assistant/services/` (pure, mostly
framework-agnostic functions) makes the pipeline unit-testable and keeps views
thin.

## 2. Major components

| Component            | Responsibility                                         |
| -------------------- | ------------------------------------------------------ |
| Views                | HTTP handling, auth/ownership checks, orchestration    |
| Forms                | Input validation (registration, upload)                |
| Models               | Persistence + invariants (constraints, indexes)        |
| `extraction.py`      | PDF/TXT text extraction with source references         |
| `chunking.py`        | Deterministic overlapping chunking                     |
| `retrieval.py`       | TF-IDF vectorization + cosine ranking                  |
| `ai_provider.py`     | Pluggable answer backend (mock / OpenAI)               |
| `usage.py`           | Atomic daily quota accounting                          |
| `documents/services` | Upload validation, private storage, processing pipeline |

## 3. Request lifecycle (a question)

1. Browser loads `/ask/` (server-rendered) listing the user's *ready* documents.
2. `ask.js` POSTs `{document_id, question}` as JSON to `/api/ask/` with the
   CSRF token from the cookie.
3. The view authenticates, validates input, verifies document ownership and
   readiness, and checks/consumes the daily quota atomically.
4. Retrieval ranks the document's chunks; the answer provider produces a
   grounded answer (or abstains).
5. The result is persisted as an `AIRequest` and returned as JSON.
6. `ask.js` renders the answer, its sources, and the updated usage counter.

## 4. Document processing pipeline

```
upload -> validate (type/size/empty) -> store privately (uuid name)
       -> create Document(status=processing)
       -> extract text (PyMuPDF / stdlib)  --fail--> status=failed + message
       -> chunk text (overlap, page refs)
       -> bulk-create DocumentChunk rows (atomic)
       -> status=ready (char/page/chunk counts)
```

A failure after the file is stored marks the document `failed` with a
user-safe message; it never leaves orphaned files or half-written chunk sets
(chunk creation + status flip happen in one transaction).

## 5. Retrieval pipeline

1. Load `DocumentChunk` rows for the selected, ownership-verified document.
2. Fit a `TfidfVectorizer` (lowercase, English stop words, unigrams+bigrams)
   over the chunk texts.
3. Transform the question with the same fitted vectorizer.
4. Compute cosine similarity; rank chunks; keep the top *K* (default 3) above
   `RETRIEVAL_MIN_SCORE`.
5. Return structured results (text, page/line reference, score) to the provider.

Retrieval is deterministic and scoped strictly to the requesting user's
authorized document.

## 6. AI provider integration

`get_provider()` returns a backend implementing `generate(question, retrieved,
document_name) -> ProviderAnswer`:

- **MockProvider** (default) — stitches the top passages into an honest,
  clearly-labelled *extractive* answer. Abstains when there is no evidence.
- **OpenAIProvider** — posts the question + retrieved context to a
  chat-completions endpoint with a strict grounding system prompt. Returns a
  sentinel (`INSUFFICIENT_CONTEXT`) → the app renders the abstain message.
  Timeouts raise `ProviderTimeout` (HTTP 503); other failures raise
  `ProviderError` (HTTP 503).

Document text is always passed as *data*, never as instructions, and the prompt
explicitly tells the model to ignore embedded directives (prompt-injection
defense).

## 7. Authentication & authorization

- Django's session auth and password hashing/validators.
- All private views use `@login_required`; the JSON API returns `401` when
  unauthenticated.
- Ownership is enforced in the query itself
  (`get_object_or_404(Model, pk=…, owner=request.user)`), so one user's access
  to another's resource returns `404` (existence is not disclosed). Chunks carry
  a denormalized `owner` for defense-in-depth during retrieval.

## 8. Usage-limit enforcement

`UsageRecord(user, date, count)` with a unique `(user, date)` constraint.
`try_consume()` runs inside a transaction using `select_for_update()` so two
concurrent requests cannot both pass the limit check. The daily boundary uses
`timezone.localdate()` (respects `DJANGO_TIME_ZONE`).

## 9. Storage decisions

Uploaded files live in `private_uploads/user_<id>/<uuid>.<ext>` — outside the
static/media web root. They are only served through the authenticated,
ownership-checked `documents:download` view, which also validates that the
resolved path stays inside the storage root (path-traversal defense).

## 10. Key architectural tradeoffs

- **Server-rendered templates + one JSON endpoint** instead of an SPA: less
  moving parts, faster to build and review, fully functional.
- **TF-IDF over embeddings/vector DB**: zero external services, deterministic,
  testable; accepts lexical-matching limitations for the MVP.
- **Synchronous processing** instead of Celery/Redis: simpler; acceptable for
  MVP document sizes. Background workers are a documented future step.
- **Mock provider by default**: the app is fully functional and testable with
  no paid API, while a real provider is a config switch away.
