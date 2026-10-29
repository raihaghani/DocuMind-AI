# DocuMind AI - System Architecture

Project: AI SaaS Workspace  
Repository: https://github.com/raihaghani/DocuMind-AI  
Review date: 28 October 2026

## Scope and reading the diagram

The diagram represents the existing Django implementation, not a generic AI SaaS reference architecture. It separates upload-time processing from question-time retrieval. Logical layers run within one Django backend; the service modules are not microservices or background workers.

The PDF and PNG use the same manually arranged landscape composition. The Mermaid source expresses the same architecture with additional error and CRUD edges; its automatic layout can differ from the publication layout. Solid outlines indicate implemented local components. Amber dashed outlines/links indicate implemented but optional configurations, not future functionality. Green boxes represent persistence. Blue arrows show execution/response flow; green arrows show persistence access. Crossing lines have no junction unless explicitly connected.

The inspected effective settings reported `django.db.backends.sqlite3` and `AI_PROVIDER=mock`. The diagram therefore identifies SQLite and MockProvider as active/default. No credentials or database account details were printed. This describes the local checkout, not an independently verified hosted deployment.

## Client and presentation

The user interacts through a web browser. Django renders HTML on the server with templates under `templates/`; Django Templates do not execute in the browser. The browser uses Bootstrap 5.3.3, Bootstrap Icons 1.11.3, custom CSS, and vanilla JavaScript. Bootstrap assets are loaded through jsDelivr. `static/js/ask.js` sends asynchronous Fetch requests to `/api/ask/`, includes `X-CSRFToken`, and displays answers, source snippets, status, and remaining usage.

Normal pages return server-rendered HTML. The ask endpoint returns JSON. The browser is drawn at both the entry and return ends conceptually, but is one client, not two applications. There is no React frontend or frontend build server.

## Application responsibilities

| Component | Responsibility and evidence |
| --- | --- |
| Django application | `config/urls.py` includes application routes. `config/settings.py` configures middleware, templates, database, storage path, and limits. WSGI/ASGI entry points exist; they do not imply a particular deployed server. |
| Authentication/authorization | `accounts/forms.py` and `accounts/views.py` implement registration and session login/logout. Middleware supports sessions, authentication, and CSRF. Ownership checks live in document/history views and the ask endpoint. Public registration/login are not themselves restricted to authenticated users. |
| Workspace management | `workspace/models.py`, `signals.py`, and `views.py` create one workspace per user and show user-scoped statistics. Creation occurs on user creation, with get-or-create fallback. |
| Document management | `documents/views.py` supports upload, list, detail, private download, and POST deletion. The question form exposes only the user's ready documents; the API independently verifies ownership and readiness. |
| Question answering | `ai_assistant/views.py:api_ask` validates input, verifies the document, consumes available quota, retrieves text, calls the selected provider, and saves the result. |
| History and usage views | `/history/` and detail routes read owned `AIRequest` records; history is paginated by 10. `/api/usage/`, the dashboard, and the ask page read usage summaries. These read paths do not invoke the answer pipeline. |

## Upload-time data flow

1. An authenticated user submits a file through `/documents/upload/`.
2. `documents/services.py:validate_upload` checks the extension (`pdf` or `txt`), nonzero size, and configured limit (default 10 MiB). The browser's MIME declaration is not treated as proof of content type.
3. `_save_file` writes the original under `private_uploads/user_<id>/<uuid>.<ext>`. `process_upload` creates `Document(status=processing)` after file storage.
4. `extraction.py` reads that stored file. PyMuPDF extracts PDF page text; TXT decoding tries UTF-8 with BOM, UTF-8, UTF-16, and Latin-1. OCR is not implemented. Corrupted, unreadable, or textless PDFs become failed documents with a message.
5. `chunking.py:build_chunks` creates overlapping text windows. Defaults are 1,000 characters with 150-character overlap. PDF chunks stay within pages; TXT chunks carry approximate line ranges.
6. A transaction bulk-creates `DocumentChunk` rows and marks the `Document` ready with counts. Recognized processing failures mark it failed. Initial file writing and metadata creation are outside this transaction; it is not a distributed filesystem/database transaction.

Upload processing is synchronous in the web request. It does not use the question quota or invoke an AI provider. Searchable text is stored as database chunk rows; original bytes remain in private file storage.

## Question-time flow and quota timing

1. The browser sends the selected `document_id` and question to `/api/ask/` as JSON (form-encoded data is also accepted).
2. Middleware and the view enforce session/CSRF behavior; the view validates question text, looks up `Document` by ID and current owner, and checks ready status. The workspace screen is a UI entry point, not an extra mandatory workspace database query on every ask.
3. `usage.py:try_consume` checks and increments today's `UsageRecord` before retrieval. Default allowance is 10 accepted questions per user/day. A transaction, a unique user/date constraint, and `select_for_update` implement accounting; SQLite lacks PostgreSQL-style row locks.
4. Exhausted requests return HTTP 429 without incrementing. Invalid or unauthorized requests also do not consume quota. Once accepted, an unsupported answer or handled provider failure still consumes quota; the default path does not refund it.
5. The application loads `document.chunks.all()` for the already-authorized document. This is where persisted chunk text enters the retrieval service; raw uploads are not re-extracted for each question.
6. TF-IDF and cosine similarity produce ranked context, then exactly one provider executes.
7. Success/unsupported responses and handled provider failures create `AIRequest`. The normal JSON response includes answer, sources, provider/mock flags, status, and a fresh usage summary. Provider failures return a friendly 503 error after saving failed history.
8. JavaScript displays the result. History can later be read independently without re-running retrieval or consuming quota.

Usage is written at acceptance, not after answer generation. The final persistence stage writes history and reads the usage summary; it does not charge the question a second time. The day boundary uses `timezone.localdate()` with configured `DJANGO_TIME_ZONE` (default UTC), so a new date selects a new counter without a scheduled reset worker.

## Retrieval and context preparation

`ai_assistant/services/retrieval.py:retrieve` fits `TfidfVectorizer` to the selected document's chunks for every accepted question. It lowercases text, removes English stop words, and uses word unigrams/bigrams. The question is transformed using the same fitted vectorizer. Cosine similarity ranks the chunks; up to `RETRIEVAL_TOP_K=3` are retained if their score is at least `RETRIEVAL_MIN_SCORE=0.05`.

Returned `RetrievedChunk` objects carry text, sequence, page/reference, source label, and score. The context box in the diagram means these in-memory results, not another database or queue. Actual prompt assembly happens inside the external provider. Empty vocabulary, no shared question vocabulary, or no sufficient scores produces no retrieved context.

No embeddings, vector database, persistent TF-IDF index, semantic search, or cross-document search is implemented. Similarity measures vocabulary overlap, not answer confidence.

## AI integration

`get_provider()` in `ai_assistant/services/ai_provider.py` selects `OpenAIProvider` only for `AI_PROVIDER=openai`; other values fall back to `MockProvider`.

- **MockProvider, active/default:** No external calls or credentials. Returns excerpts from the retrieved passages with labels (up to 500 characters per passage). Empty context produces the insufficient-information response. This is extractive behavior, not generative reasoning.
- **OpenAIProvider, optional implemented path:** Requires `AI_API_KEY`. Formats labeled context and a grounding prompt, then uses Python `urllib.request` to POST to `AI_BASE_URL` plus `/chat/completions`. Default model is `gpt-4o-mini`; default base URL is `https://api.openai.com/v1`; timeout is 30 seconds. These are configuration defaults, not a claim about current service-side availability. The external boundary receives the question, document name, and retrieved text, not the full original file as a file upload.
- **Result:** `ProviderAnswer` carries answer, supported status, provider/mock metadata, and source references. Sources include page/label, a snippet (up to 240 characters before ellipsis), and retrieval score. External responses containing `INSUFFICIENT_CONTEXT` become unsupported. Missing credentials are checked before empty-context handling in the real provider.

The two providers are alternatives, never a sequential pair. The single provider box in the publication layout groups the local adapter and its optional remote HTTP service; Mermaid separates those nodes for clarity. Grounding is a prompting/extractive design intent, not a formal factual guarantee or a complete prompt-injection defense.

## Data layer and connections

SQLite at `BASE_DIR/db.sqlite3` is the active local database. All model access uses Django's ORM. Boxes within the database group are logical model groups in this one database, not separate stores.

| Model | Relationships and data |
| --- | --- |
| `django.contrib.auth.models.User` | Built-in identity model; authentication data. Default database-backed Django `Session` supports sessions. |
| `Workspace` | One-to-one `owner` to User; name and creation timestamp. |
| `Document` | Foreign keys to owner and workspace; metadata, file path, status, counts, and processing error. |
| `DocumentChunk` | Foreign keys to document and owner; sequence, text, page/reference. Unique document/sequence. |
| `AIRequest` | Foreign key to user and nullable document; name snapshot, question, answer, sources, status, provider, error, timestamp. No direct Workspace foreign key. |
| `UsageRecord` | User/date/count with a unique user/date constraint. |

Arrow semantics: document processing writes metadata/chunks; retrieval reads chunk text; authentication/workspace views access identity/session/workspace rows; quota reads and updates `UsageRecord`; result handling writes `AIRequest` and reads usage. Diagram ORM access lines are schematic connections, not SQL execution order. Additional dashboard/history reads and document CRUD are shown in Mermaid and described here to avoid crowding the publication layout.

Private originals are outside public static/media routing. An authenticated download view checks ownership and resolved-path containment before streaming the file. Deletion cascades to chunks, sets related `AIRequest.document` to null, and attempts filesystem deletion. History retains the document name, answer, and snippets. The storage box is local filesystem storage, not S3 or another remote service.

**PostgreSQL is an optional backend alternative, not the active database or a replica.** `config/settings.py` parses a postgres/postgresql `DATABASE_URL`. A PostgreSQL driver is absent from `requirements.txt`; one must be installed separately. The parser does not forward options such as `sslmode`. Switching backend does not migrate existing SQLite data or files automatically.

## Architectural decisions and boundaries

The design combines Django's built-in authentication, ORM, templates, and admin with focused service modules. It keeps deployment simple and makes retrieval and mock answering usable without external AI infrastructure. TF-IDF trades semantic matching quality for deterministic local retrieval. Synchronous uploads/answers avoid worker infrastructure but tie processing latency to web requests. Local files and SQLite simplify development but require deliberate backup, storage, and concurrency planning for deployment.

The diagram does not show Celery/Redis, OCR, embedding search, vector databases, S3 storage, billing, or team collaboration as implemented. Such capabilities are absent or described as future ideas in project documentation; they are not runtime architecture nodes. Error handling is also bounded: retrieval occurs outside the provider exception handler, and unexpected input/provider shapes may escape friendly error responses.

## Verification and source map

Inspected `config/settings.py`, root and all app URL files, app models/views/forms, migrations, `requirements.txt`, `.env.example`, frontend templates/JavaScript, and document/AI services. The most important implementation anchors are:

- `documents/services.py`: `validate_upload`, `_save_file`, `process_upload`, `delete_document`.
- `ai_assistant/services/extraction.py`: PDF/TXT extraction dispatch and errors.
- `ai_assistant/services/chunking.py`: chunk construction and source references.
- `ai_assistant/services/retrieval.py`: per-question TF-IDF fit and cosine ranking.
- `ai_assistant/services/ai_provider.py`: provider selection, source generation, HTTP boundary.
- `ai_assistant/services/usage.py`: consumption before processing and local-day summaries.
- `ai_assistant/views.py`: input/ownership/readiness validation, pipeline ordering, persistence and JSON.
- `documents/models.py`, `workspace/models.py`, `ai_assistant/models.py`: actual persistence entities and relationships.
- `templates/base.html`, `templates/ai_assistant/ask.html`, `static/js/ask.js`: server templates, Bootstrap versions, Fetch and response display.

Mermaid syntax is parser-validated. The PDF is a single landscape page; its rendered page and the high-resolution PNG were visually checked for readable labels and overlapping elements. No Lucidchart creation is claimed. No production deployment or live external AI call was performed.
