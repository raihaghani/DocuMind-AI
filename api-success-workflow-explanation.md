# DocuMind AI - API success workflow

Verified on 2026-10-29 against the local project at commit `9e94795386b976d4203f50f080b0a0e393bb2f3a`. This is an implementation-derived successful workflow, not a captured API execution. No question was submitted, no external AI call was made, and no application data or schema was changed.

## 1. Endpoint and HTTP method

**POST `/api/ask/`**, Django route name `ai_assistant:api_ask`.

`config/urls.py` includes `ai_assistant.urls` at the root. That URL module maps `api/ask/` to `views.api_ask`, decorated with `@require_POST`. Django's URL resolver was run and returned `/api/ask/`. The frontend uses `window.DOCUMIND_ASK_URL || "/api/ask/"`; the inspected templates do not set an override.

The separate `GET /ask/` page supplies the current user's READY documents and initial usage summary. It is a prerequisite to the diagram, not an additional call made by the question submission. The diagram begins with that page already loaded and the user selecting an uploaded document.

## 2. Authentication and authorization

Authentication is Django session authentication, not bearer-token or JWT authentication. SessionMiddleware and AuthenticationMiddleware provide the session and lazy `request.user`; `_require_auth_json(request)` explicitly checks `request.user.is_authenticated` inside the API view. The API does not use the page view's `@login_required` decorator.

CsrfViewMiddleware remains enabled. `ask.js` reads the `csrftoken` cookie and sends its value as `X-CSRFToken`. Same-origin fetch sends the session cookie under the browser's default same-origin credentials policy. The authenticated base template contains a CSRF token in its logout form. Successful CSRF processing is a precondition; the diagram combines middleware and view concerns on the Django lifeline. Session/user loading is shown as one logical storage interaction, not an assertion of an exact SQL-query count.

Authorization occurs in `Document.objects.get(pk=document_id, owner=request.user)`. The view then requires `document.status == Document.Status.READY`. It does not authorize via workspace membership. No separate authorization service exists. Ownership and readiness checks occur **before** quota consumption.

## 3. Request format

The browser submits `Content-Type: application/json` with exactly these application fields:

| Field | Frontend type | Meaning / implementation validation |
|---|---|---|
| `document_id` | String from the select element | Required, truthy primary key of an owned document; passed to the ORM PK lookup. |
| `question` | String | Trimmed in browser and backend; must be nonempty and no longer than `MAX_QUESTION_LENGTH`, currently 1000. |

Illustrative request only; ID 42 is not asserted to exist:

```http
POST /api/ask/
Content-Type: application/json
X-CSRFToken: <valid token>
Cookie: sessionid=<authenticated session>; csrftoken=<token>

{"document_id":"42","question":"How many paid leave days are available?"}
```

The view also accepts form fields through `request.POST` for non-JSON content types. The diagram follows the actual JSON frontend. This describes implemented validation, not a formal JSON schema that the application enforces for arbitrary input types.

## 4. Effective configuration and scenario

Only non-secret settings were inspected after loading the project configuration:

| Setting / component | Effective value |
|---|---|
| Database | SQLite (`db.sqlite3`) |
| Session backend | `django.contrib.sessions.backends.db` |
| `AI_PROVIDER` / `get_provider()` | `mock` / `MockProvider` |
| `DAILY_QUESTION_LIMIT` | 10 |
| `MAX_QUESTION_LENGTH` | 1000 |
| `RETRIEVAL_TOP_K` | 3 |
| `RETRIEVAL_MIN_SCORE` | 0.05 |
| `TIME_ZONE` | UTC |

The documented scenario assumes a signed-in user, valid CSRF token, an owned READY document, available quota, and nonempty relevant retrieval results. It produces `status="success"`, `supported=true`, `provider="mock"`, and `is_mock=true`.

The implementation also contains `OpenAIProvider`, selected only when `AI_PROVIDER` is `openai`. It posts the configured model, system/user messages and `temperature=0` to `AI_BASE_URL.rstrip("/") + "/chat/completions"`, using `AI_API_KEY` for bearer authorization and the configured timeout. That alternate configuration is **not** the active path in the diagram. The configured mock executes locally and performs extractive passage assembly, not model-based reasoning.

## 5. Workflow interactions

1. **User and browser:** The user selects a document and submits a question. `ask.js` trims the question, captures the selected option's filename, enables its loading state and sends the JSON POST.
2. **Django authentication:** Middleware handles session/CSRF concerns and supplies lazy user identity. `@require_POST` accepts the method, and `_require_auth_json` verifies authentication. Resolving the user uses the session-backed authentication machinery; the diagram combines those reads into one logical database interaction.
3. **Input validation:** The view parses JSON, strips the question and checks question presence, maximum length and document ID presence.
4. **Document authorization:** The ORM fetches the document by both primary key and owner. The view confirms its READY status.
5. **Daily accounting transaction:** `try_consume(user)` computes `timezone.localdate()` (UTC in this configuration). Inside `transaction.atomic()`, it calls `UsageRecord.objects.select_for_update().get_or_create(user=user, date=today)`. An absent row begins at count zero. It checks `count < limit`, saves `F("count") + 1` and exits the transaction before returning `True`.
6. **Chunk retrieval:** The view constructs `document.chunks.all()` and passes this lazy queryset to `retrieve`. The query is evaluated by `list(chunks)` inside that service. Default chunk ordering is `document_id, seq`. The chunk query is restricted to the already-authorized document; it does not independently filter `owner`.
7. **Ranking:** `TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2))` fits on chunk texts only, then transforms the question. The service computes cosine similarity, sorts descending, considers the top three candidates and excludes scores below 0.05. It returns `RetrievedChunk` objects containing sequence, text, page number, reference, source label and score rounded to four decimal places. Threshold comparison uses the unrounded score. There is no embedding service, vector database, or stored TF-IDF index in this path.
8. **Provider selection and generation:** `get_provider()` returns `MockProvider`. The view calls `generate(question, retrieved, document.original_filename)`. The provider builds source metadata, trims each retrieved passage, limits passage excerpts to 500 characters before appending an ellipsis where needed, prefixes source labels, and joins the passages into an answer naming the document. With retrieved context present it returns a successful `ProviderAnswer`.
9. **History write:** The view maps `result.supported` to `AIRequest.Status.SUCCESS` and invokes `_save_request`. This inserts one AIRequest using the authenticated user, selected document, filename snapshot, question, answer, provider, source list and empty error detail. The ORM sets `created_at` automatically and returns the inserted object's ID.
10. **Usage refresh:** The view calls `get_usage_summary(user)`, which reads today's UsageRecord and computes `used`, `limit`, `remaining`, `percent` and `at_limit`. This does not consume another unit. The date is recalculated, so a request spanning local midnight can read the new day's summary after consuming the prior day's quota; no date is carried forward from `try_consume`.
11. **API return:** A `JsonResponse` returns HTTP 200 with the eight top-level fields documented below. JSON return arrows represent response values; solid arrows represent calls. Activation bars mark the participating processing intervals.
12. **Frontend display:** `response.json()` is parsed and `response.ok` selects `showAnswer`. The browser shows the success badge, writes answer text using `textContent`, renders source labels/snippets/relevance scores alongside the previously selected filename, shows the mock-provider notice and updates the `remaining/limit` badge. The promise's `finally` handler clears loading and reenables the button. There is no additional `/api/usage/` request in this success path.

## 6. Response format

**HTTP 200**, `Content-Type: application/json`. The response object is:

| Top-level field | Type | Meaning in this success scenario |
|---|---|---|
| `id` | Integer | Newly persisted AIRequest primary key. |
| `status` | String | `"success"`. |
| `answer` | String | Local mock's extractive answer. |
| `supported` | Boolean | `true`. |
| `is_mock` | Boolean | `true`; used to display the mock notice. |
| `provider` | String | `"mock"`. This maps to history field `provider_mode`. |
| `sources` | Array of objects | Provider-built citation metadata, detailed below. |
| `usage` | Object | Current daily usage summary. |

| `usage` field | Type | Computation |
|---|---|---|
| `used` | Integer | Today's stored count, or zero if absent. |
| `limit` | Integer | Configured daily limit. |
| `remaining` | Integer | `max(limit - used, 0)`. |
| `percent` | Integer | `int(min(used / limit, 1) * 100)` when limit is nonzero; otherwise zero. |
| `at_limit` | Boolean | `used >= limit`. |

There is no `document_id`, `document_name`, timestamp or separate remaining-quota field at response top level. The response's status string is separate from the HTTP status code. This document deliberately omits failure branches and the HTTP-200 unsupported-answer branch from the sequence.

## 7. Data persistence and transaction boundaries

**Usage is consumed first**, before chunk ranking and provider generation. It is not deferred to answer delivery and is not just a temporary reservation finalized later. `UsageRecord` is unique on `(user, date)` via `unique_usage_per_user_per_day`; `count` defaults to zero. SQLite does not implement SELECT FOR UPDATE row locks, so the code's use of `select_for_update()` must not be interpreted as a verified PostgreSQL-style locking guarantee on SQLite.

**History is inserted later**, after the provider returns. The saved fields are `user`, `document`, `document_name`, `question`, `answer`, `status`, `provider_mode`, `sources`, `error_detail`, plus generated `id` and `created_at`. `supported` and `is_mock` are returned by the provider and API but are not AIRequest columns. `sources` is stored in its JSONField, not a separate source table.

Usage and history are not enclosed by a single shared transaction, and there is no FK from UsageRecord to AIRequest. The successful sequence writes usage once, writes history once, then rereads usage. No refund is part of this path. Document deletion later sets `AIRequest.document` to NULL while retaining the filename snapshot and text history.

The diagram combines request-history storage, document/chunk storage, usage storage and session-backed user reads on the SQLite/ORM lifeline because they use the application's database; it does not invent a separate history service.

## 8. Source references and display

The provider's `_build_sources(retrieved)` creates each source object:

| Field | Type | Origin |
|---|---|---|
| `label` | String | `DocumentChunk.source_label`: `Page N`, otherwise `reference`, otherwise `Chunk seq+1`. |
| `page` | Integer or null | Retrieved chunk's `page_number`. |
| `snippet` | String | Stripped text with newlines replaced by spaces; if longer than 240 characters, take the first 240, rstrip and append an ellipsis. |
| `score` | Number | Cosine similarity rounded to four decimal places by retrieval. |

The view passes `result.sources` through unchanged to history and the JSON response; sources are built by the provider adapter, not attached by a separate backend service after generation. The actual source payload has **no `document` key**, despite the older descriptive comment on the model's JSONField. The frontend gets the filename from the selected dropdown option captured before the fetch, not from the source object. It displays the label, snippet and relevance score, and escapes inserted source strings. The `page` value is returned but is not separately rendered by `ask.js`; the label already carries a page reference where available.

## 9. Verification and source map

The local implementation is authoritative for this artifact. The repository URL is project identification; this is not a claim to have verified a remote deployment or its configuration.

| Source | Evidence |
|---|---|
| `config/urls.py`, `ai_assistant/urls.py` | Root include, exact route, view mapping. |
| `config/settings.py` | Middleware, SQLite, session defaults, effective limits and provider settings. |
| `ai_assistant/views.py`: `api_ask`, `_require_auth_json`, `_save_request` | Request parsing, ownership/readiness checks, service ordering, persistence and response keys. |
| `ai_assistant/services/usage.py` | Early transactional consumption, date boundary, post-answer summary. |
| `ai_assistant/services/retrieval.py` | Lazy queryset evaluation, TF-IDF configuration, cosine ranking and filtering. |
| `ai_assistant/services/ai_provider.py` | Actual provider selection, local mock, optional OpenAI path, source payload. |
| `ai_assistant/models.py` | History fields, automatic timestamp, usage uniqueness. |
| `documents/models.py` | Chunk relationship, default ordering and source-label property. |
| `static/js/ask.js` | Fetch method/body/CSRF header, answer/source rendering and usage display. |
| `templates/ai_assistant/ask.html`, `templates/base.html` | Document dropdown, answer UI, mock notice and authenticated CSRF-bearing template. |

Verification scope: source inspection, runtime URL resolution and non-secret settings/provider-class inspection. No live API success is claimed. Mermaid parsed successfully. The final PDF is one large landscape vector page; it was rendered with Poppler and visually checked for label clipping, arrow spacing and lifelines. PDF text extraction confirmed the endpoint, HTTP 200, provider, quota, retrieval and history interactions. The PNG decoded successfully at 4949 x 4418 pixels and was visually inspected. PDF and PNG render the same Mermaid source. Use zoom or large-format printing; reducing this complete sequence to A4 would make labels small.
