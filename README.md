# DocuMind AI

## 1. Project README and Setup Guide

**Project type:** AI SaaS Workspace

**Repository:** https://github.com/raihaghani/DocuMind-AI

**Technology stack:** Python 3.12, Django 5.2.18, Django Templates, Bootstrap 5.3.3, SQLite, PyMuPDF 1.24.14, scikit-learn 1.5.2, NumPy 2.1.3, and python-dotenv 1.0.1. PostgreSQL configuration and an optional OpenAI-compatible answer provider are implemented.

**Documentation date:** 28 October 2026

This guide describes the inspected local implementation. Source code, settings, migrations, templates, tests, dependency pins, and `.env.example` are the authority for the behavior documented here. Proposed enhancements elsewhere in `docs/` are not presented as implemented features.

<!-- pagebreak -->

## 2. Project Overview

DocuMind AI is a Django web application for asking questions about private PDF and TXT documents. Each registered user has an individual workspace with document management, question history, and a daily question allowance.

The application addresses the time spent manually locating facts in documents. Intended users include students, researchers, and professionals working with notes, policies, or reports. These are use cases for the workflow, not separate application roles. Its objective is to make document information easier to find while showing the passages behind each response.

### How document-based answering works

1. A user uploads a PDF containing selectable text or a TXT file.
2. Django stores the file privately, extracts text, and persists overlapping chunks with page or approximate line references.
3. The user selects one ready document and submits a question.
4. The application verifies ownership and readiness, then consumes one available daily question.
5. TF-IDF and cosine similarity rank the selected document's chunks. By default, up to three chunks scoring at least 0.05 are selected.
6. The default mock provider returns excerpts without an API key. The optional external provider receives the question, document name, and selected context to generate an answer.
7. The answer, references, provider, and status are saved in history. Empty retrieval produces an insufficient-information response; the external provider can also signal insufficient context.

Retrieval scores measure lexical similarity, not factual confidence. The application does not guarantee that every generated statement is supported by a retrieved passage.

### Guide map

Sections 3-5 cover features, technologies, and architecture. Sections 6-9 cover prerequisites, installation, configuration, and the database. Sections 10-11 explain operation and testing. Sections 12-14 provide the directory map, limitations, and repository references.

## 3. Implemented Features

- **Registration and authentication:** Required username/email, confirmed password, case-insensitive duplicate checks in the registration form, Django password validation, session login, and POST-only logout. Login uses username and password.
- **Private workspaces:** One workspace per user, created by a user-creation signal or on first access. Dashboard statistics come from user-scoped database queries.
- **Document management:** Upload, list, inspect, download, and delete owned documents. Downloads enforce ownership and check that the resolved file path stays inside private storage.

<!-- pagebreak -->

### Document processing and answering

| Capability | Implemented behavior |
| --- | --- |
| PDF and TXT uploads | Extension, nonzero-size, and upload-size validation. Default maximum is 10 x 1024 x 1024 bytes. |
| Text extraction | PyMuPDF extracts PDF pages. TXT decoding tries UTF-8 with BOM, UTF-8, UTF-16, then Latin-1. |
| Chunking | Default target of 1,000 characters with 150-character overlap; PDF page references and approximate TXT line ranges. Chunks persist in the database. |
| TF-IDF retrieval | Lowercase text, English stop words, word unigrams/bigrams, and cosine-similarity ranking over one selected document. |
| Answer providers | Extractive mock responses or optional external generation using retrieved context. |
| Source references | Label, page when applicable, snippet, and similarity score. The UI associates each source with the document name. |
| Question history | User-specific, newest-first list with 10 entries per page; successful, unsupported, and handled provider-failure requests. History survives document deletion. |
| Error handling | Invalid inputs receive messages; extraction failures mark documents failed. Handled provider errors/timeouts return HTTP 503 and create failed history entries. |
| Daily usage | Database-backed counters; default 10 accepted questions per user per day. Dashboard and Ask AI show remaining usage. |

### Daily usage accounting

An accepted question consumes quota before retrieval and provider execution. Unsupported answers and handled provider failures still count. Invalid input, unauthorized or unready documents, and over-limit rejections do not count.

The daily boundary uses `DJANGO_TIME_ZONE`, default UTC. A new date uses a new counter without a scheduled reset job. Transactions, a unique user/date constraint, and `select_for_update()` support updates. SQLite does not provide PostgreSQL-style row locking; the sequential tests do not establish concurrent quota guarantees.

Implementation evidence is in `accounts/forms.py`, app views and models, `documents/services.py`, and `ai_assistant/services/`. CSRF middleware is enabled, and the JavaScript question client sends a CSRF token.

<!-- pagebreak -->

## 4. Technology Stack

| Component | Technology | Purpose |
| --- | --- | --- |
| Language | Python 3.12; tested here on 3.12.10 | Application and management commands. |
| Web framework | Django 5.2.18 | Routing, ORM, sessions, forms, templates, migrations, admin, and CSRF protection. |
| Frontend | Django Templates, HTML, custom CSS, vanilla JavaScript | Server-rendered pages and Fetch-based question submission. |
| UI libraries | Bootstrap 5.3.3; Bootstrap Icons 1.11.3 | Layout, components, and icons loaded through jsDelivr. |
| Default database | SQLite | Local `db.sqlite3`; no separate server. Version is not pinned. |
| Optional database | PostgreSQL | Selected by `DATABASE_URL`; driver installation is separate. |
| PDF extraction | PyMuPDF 1.24.14 | Selectable text extraction; imported as `fitz`. |
| Retrieval | scikit-learn 1.5.2 | TF-IDF vectorization and cosine similarity. |
| Numerical support | NumPy 2.1.3 | Numerical dependency for the retrieval stack. |
| Configuration | python-dotenv 1.0.1 | Loads the root `.env` file. |
| Answer providers | Built-in mock; Python `urllib.request` | Extractive responses or an OpenAI-compatible HTTP endpoint; no provider SDK. |
| Storage | Local filesystem | Private per-user directories with UUID filenames. |
| Tests | Django `TestCase`, `override_settings`, `unittest.mock` | Database-backed tests and simulated provider responses. |

Python package versions are pinned in `requirements.txt`; frontend versions come from `templates/base.html`. There is no Node.js build step, vector database, embedding model, Redis, or background task queue in the inspected application.

## 5. Project Architecture Overview

The browser receives Django templates from four apps. `accounts` handles authentication; `workspace` owns the single-user workspace and dashboard; `documents` manages uploads and storage; `ai_assistant` handles questions, retrieval, providers, history, and usage. Root routing lives in `config/urls.py`.

```text
Browser -> Django routes/views -> Templates / JSON
                      |
                      +-> ORM -> SQLite or PostgreSQL
                      +-> Private local document files
                      +-> Extract -> Chunk -> Retrieve
                                             -> Answer provider
                                             -> Saved history
```

<!-- pagebreak -->

### Processing and persistence

`documents/services.py` orchestrates validation, file storage, metadata creation, extraction, and chunk persistence. Processing is synchronous. Chunk creation and the ready-status update share a transaction. Recognized extraction failures leave a failed record and its stored file available for inspection or deletion.

The extraction, chunking, retrieval, provider, and usage modules live in `ai_assistant/services/`. Retrieval fits a new TF-IDF vectorizer for each question; no persistent search index is maintained.

| Model | Relationship and stored information |
| --- | --- |
| Django User | Authentication identity; owns a workspace, documents, requests, and usage records. |
| Workspace | One-to-one owner; name and creation time. |
| Document | Owner/workspace; names, storage path, type, size, status, counts, and processing error. |
| DocumentChunk | Document/owner; sequence, text, optional page, and reference. Document/sequence is unique. |
| AIRequest | User and nullable document; document-name snapshot, question, answer, status, provider, sources, error, and timestamp. |
| UsageRecord | User, date, and count; unique user/date constraint. |

Deleting a document cascades to its chunks and attempts to remove its original file. The request's document link becomes null, but history retains answers and source snippets. Document deletion does not erase all document-derived text.

Uploads reside under `private_uploads/user_<id>/<uuid>.<ext>` and have no public media route. Mock answering is local. External provider mode sends retrieved text, the question, and document name to the configured service.

## 6. Installation Requirements

Use Python 3.12 for this setup. The existing environment is Python 3.12.10, and the original project guidance targets 3.12. No formal Python-version manifest exists. NumPy 2.1.3 declares Python 3.10 or later, but this does not establish compatibility of every interpreter/dependency combination.

Install Git, Python with pip and venv, and use Windows PowerShell plus a modern browser. Commands below assume the Windows `py` launcher can select Python 3.12. Internet access is needed for cloning, packages, CDN assets, and external provider calls. Mock answering requires no API credentials or network service.

The application needs write access to its database and private upload directory. SQLite requires no database account. PostgreSQL requires a running server, an existing database/user, and a separately installed compatible Python driver. The five direct Python dependencies are listed in Section 4; pip resolves transitive dependencies.

<!-- pagebreak -->

## 7. Installation Instructions

### 7.1 Clone and create the environment

Run in PowerShell from the desired parent directory:

```powershell
git clone https://github.com/raihaghani/DocuMind-AI.git
Set-Location .\DocuMind-AI
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For the existing checkout, skip cloning and first run:

```powershell
Set-Location 'C:\Users\raiha\OneDrive\Desktop\DocuMind AI'
```

If PowerShell blocks activation, invoke the interpreter directly for all Python commands; no execution-policy change is required:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py check
```

### 7.2 Configure environment variables

Create `.env` only if it does not already exist, then generate a fresh key:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Open `.env` in your editor. Set `DJANGO_SECRET_KEY` to the generated value, retain `DJANGO_DEBUG=True` for local use, leave `DATABASE_URL` blank for SQLite, and keep `AI_PROVIDER=mock` for credential-free answering. Do not commit `.env` or publish the generated key.

### 7.3 Initialize and start

```powershell
python manage.py migrate
python manage.py check
python manage.py runserver
```

Open `http://127.0.0.1:8000/`; stop the server with Ctrl+C. Optionally run `python manage.py createsuperuser` for `/admin/`. Ordinary users register through `/register/`.

After configuration and migrations, `.\run.ps1` is an alternative launcher. It uses the local `.venv`, checks PDF/retrieval imports, attempts dependency installation if those imports fail, and invokes `runserver`. It does not create `.env` or apply migrations.

Commands match the actual root layout and Django entry point. Cloning and a clean-environment installation were not executed as validation steps.

<!-- pagebreak -->

## 8. Environment Configuration

`config/settings.py` loads `.env` beside `manage.py`. Existing process variables take precedence because `load_dotenv()` does not enable override. Empty values use defaults. Invalid integer/float text also falls back; numeric ranges are not generally validated. Boolean true values are `1`, `true`, `yes`, and `on`, case-insensitively.

No variable is mandatory for a default local mock run. A secure secret is needed for safe deployment; an API key is required for external provider use. The tables list settings defaults, which may differ from `.env.example` placeholders.

### 8.1 Django and database settings

| Variable | Default | Requirement and purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | `django-insecure-dev-key-change-me` | Optional only locally; replace with a secure random value. Debug-off startup rejects the `django-insecure` prefix. The example's different `change-me` placeholder must also be replaced. |
| `DJANGO_DEBUG` | `True` | Optional. Development debug mode; use `False` for deployment. |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Optional locally. Comma-separated accepted hosts; set actual deployment hosts. |
| `DATABASE_URL` | Unset | Optional. Blank means SQLite; otherwise use `postgres://` or `postgresql://`. |
| `DJANGO_TIME_ZONE` | `UTC` | Optional. Display timezone and daily usage boundary. Use a valid name, such as `Asia/Karachi`. |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` with debug off | Optional; read only when debug is off. HTTP-to-HTTPS redirection. Absent from `.env.example`. |
| `DJANGO_SECURE_HSTS_SECONDS` | `31536000` with debug off | Optional; read only when debug is off. HSTS duration in seconds. Absent from `.env.example`. |

With debug disabled, settings also enable secure session/CSRF cookies, HSTS subdomains/preload, content-type sniffing protection, and frame denial. The configured proxy HTTPS header must correspond to a trusted deployment proxy. These settings do not supply hosting infrastructure.

No actual `.env` secrets are reproduced here.

<!-- pagebreak -->

### 8.2 Application limits and retrieval

| Variable | Default | Requirement and purpose |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE_MB` | `10` | Optional. Per-file limit; units are 1024 x 1024 bytes. |
| `DAILY_QUESTION_LIMIT` | `10` | Optional. Accepted questions per user/day. Zero blocks questions. |
| `CHUNK_SIZE` | `1000` | Optional. Target characters per chunk; use a positive value. Not in `.env.example`. |
| `CHUNK_OVERLAP` | `150` | Optional. Overlap characters; use a nonnegative value smaller than chunk size. Not in `.env.example`. |
| `RETRIEVAL_TOP_K` | `3` | Optional. Maximum ranked chunks; use a positive value. |
| `RETRIEVAL_MIN_SCORE` | `0.05` | Optional. Minimum cosine-similarity score. |
| `MAX_QUESTION_LENGTH` | `1000` | Optional. Server-side character limit. Not in `.env.example`; the HTML field separately hardcodes 1,000. |

### 8.3 Answer provider

| Variable | Default | Requirement and purpose |
| --- | --- | --- |
| `AI_PROVIDER` | `mock` | Optional. `openai` selects HTTP answering; all other values currently fall back to mock. |
| `AI_API_KEY` | Unset | Required for external provider use only; sent as a bearer token. |
| `AI_MODEL` | `gpt-4o-mini` | Optional. Model identifier passed to the service; availability is not validated here. |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Optional. Client appends `/chat/completions` after stripping a trailing slash. |
| `AI_REQUEST_TIMEOUT` | `30` | Optional. HTTP timeout in seconds. |

For external answering, set `AI_PROVIDER=openai`, enter your key in `AI_API_KEY`, and configure model/base URL for a compatible service. Restart the server after changing settings. The client posts model/messages/temperature and expects `choices[0].message.content`; service compatibility is conditional on that format.

Mock responses use up to 500 characters per retrieved chunk. Source snippets use up to 240 characters, followed by an ellipsis if truncated. The external prompt requests citations and an `INSUFFICIENT_CONTEXT` signal when unsupported. These are prompting controls, not formal factual verification.

<!-- pagebreak -->

## 9. Database Setup

### SQLite initialization

With `DATABASE_URL` unset or blank, Django uses root-level `db.sqlite3`. It is Git-ignored and is not required in a fresh clone. Initialize and inspect the schema with:

```powershell
python manage.py migrate
python manage.py showmigrations
```

Initial application migrations exist in `workspace`, `documents`, and `ai_assistant`, each under `migrations/0001_initial.py`. They create workspace, document/chunk, request, and usage tables, indexes, and uniqueness constraints. Built-in migrations create Django authentication, session, admin, and content-type tables. `accounts` uses Django's built-in user model and has no custom initial model migration.

For normal setup, apply committed migrations; do not create replacements. After intentional model edits, developers can run `makemigrations`, review the generated files, and then apply them.

### PostgreSQL support

Settings implement PostgreSQL URL parsing and Django's PostgreSQL backend. However, neither `psycopg` nor `psycopg2` is in `requirements.txt`. Provision the database/user and install a compatible driver separately before selecting this backend. PostgreSQL was not exercised during this documentation task.

The supported URL structure is a template, not a credential:

```text
postgresql://USER:PASSWORD@HOST:5432/DATABASE_NAME
```

The parser reads database, username, password, hostname, and port. It does not forward query options such as `sslmode` or explicitly URL-decode credentials. Confirm that connection requirements fit this implementation, set `DATABASE_URL`, and run `python manage.py migrate` against the selected database.

Changing the URL switches databases; migrations do not transfer existing SQLite data or uploaded files. Back up both the database and `private_uploads/` when preserving application state.

## 10. Running the Application

From the configured root, start Django's development server:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Visit `http://127.0.0.1:8000/`. This is a development server command; the repository does not include a complete production hosting configuration.

<!-- pagebreak -->

### User workflow

1. Open `/register/` and enter username, email, and confirmed password. Registration logs you in and creates a workspace. Password checks include minimum length eight and common/numeric/similarity validation.
2. For later sessions, open `/login/` and use username/password. The logout button submits POST.
3. Open `/documents/upload/`, select a PDF or TXT, and submit. Inspect ready/failed status, extracted counts, and any processing message.
4. Open `/ask/`, select a ready document, and ask a question using terms found in it. The page displays the answer, sources, status, and usage balance.
5. Open `/history/` and select an entry for its answer, provider, timestamp, references, or failure message.
6. Check `/dashboard/` for totals and today's used/remaining allowance. Ask AI also shows remaining questions.

A manual exercise: upload a TXT file containing `Employees receive 20 days of annual paid leave.` Ask `How many paid leave days do employees receive?` Expected mock behavior is a labeled excerpt with a line reference. This is an exercise, not a recorded browser test.

### Implemented routes

| Route | Use |
| --- | --- |
| `/` | Public landing page; logged-in users redirect to dashboard. |
| `/register/`, `/login/`, `/logout/` | Registration/login forms; POST-only logout. |
| `/account/`, `/dashboard/` | Private account summary and workspace statistics. |
| `/documents/`, `/documents/upload/` | Document list and GET/POST upload form. |
| `/documents/<id>/` | Owned-document details. |
| `/documents/<id>/download/` | Ownership-checked file download. |
| `/documents/<id>/delete/` | POST-only deletion. |
| `/ask/`, `/history/`, `/history/<id>/` | Question form and private request history. |
| `/api/ask/` | POST JSON or form fields `document_id` and `question`. |
| `/api/usage/` | GET user usage summary as JSON. |
| `/admin/` | Django administrator interface. |

Private HTML pages require login. JSON endpoints require a session, and question POSTs require CSRF validation; the frontend sends `X-CSRFToken`. Handled errors use 400, 401, 404, 429, or 503. CSRF rejection can occur first with 403. Unsupported answers return HTTP 200 with status `unsupported`.

<!-- pagebreak -->

## 11. Testing Instructions

Run from the root using the configured virtual environment:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 1
```

To narrow a run:

```powershell
python manage.py test ai_assistant
python manage.py test ai_assistant.tests.AskApiTests
```

The suite uses Django's default test runner and `TestCase`. No separate pytest configuration or test settings module exists. Tests use a test database and temporary upload storage. Mock answering and mocked provider calls avoid paid external API requests.

| Test file | Existing coverage |
| --- | --- |
| `accounts/tests.py` | Registration, duplicate username, password checks, login/logout, invalid login, and protected-page redirects. |
| `workspace/tests.py` | Workspace creation, idempotent access, dashboard counts. |
| `documents/tests.py` | PDF/TXT processing, rejected/corrupt/textless uploads, ownership checks, download and deletion. |
| `ai_assistant/tests.py` | Chunking, retrieval, providers, usage, API statuses, private history, and retention after deletion. |

### Executed validation - 28 October 2026

Using the existing Python 3.12.10 environment, these commands completed successfully:

| Check | Observed result |
| --- | --- |
| `manage.py check` | No issues; 0 silenced. |
| `manage.py makemigrations --check --dry-run` | No changes detected. |
| `manage.py test --verbosity 1` | 45 tests ran in 70.924 seconds; OK; exit code 0. |

The test database was created and destroyed by Django. Initial sandbox launches could not access the underlying interpreter; running outside that restriction succeeded. This was not a missing-Python defect. Expected logs included rejected access, quota limits, simulated provider unavailability, and failed PDF extraction.

No live external-provider request, PostgreSQL run, fresh installation, or interactive browser walkthrough is claimed. The suite does not establish concurrent quota behavior or exhaustive input validation. Its default Django test client does not enforce CSRF checks; the tests do not explicitly enable that option.

If imports fail, use `.\.venv\Scripts\python.exe` explicitly and install dependencies into that interpreter. Image-only PDFs require a selectable-text version. For provider errors, check configuration/connectivity; accepted failures still consume quota. HTTP 429 means the daily allowance is exhausted.

<!-- pagebreak -->

## 12. Project Directory Structure

This condensed map shows observed application paths and the two deliverables. Real files/directories are grouped on some lines. Dependency internals, caches, Git internals, private filenames, and documentation-build intermediates are omitted.

```text
DocuMind AI/
|-- accounts/
|   |-- forms.py, views.py, urls.py, models.py, tests.py
|   `-- migrations/__init__.py
|-- workspace/
|   |-- models.py, signals.py, views.py, urls.py, tests.py
|   `-- migrations/0001_initial.py
|-- documents/
|   |-- models.py, forms.py, services.py, views.py, urls.py, tests.py
|   `-- migrations/0001_initial.py
|-- ai_assistant/
|   |-- models.py, views.py, urls.py, tests.py
|   |-- migrations/0001_initial.py
|   `-- services/
|       |-- extraction.py, chunking.py, retrieval.py
|       `-- ai_provider.py, usage.py
|-- config/
|   `-- settings.py, urls.py, asgi.py, wsgi.py
|-- templates/
|   |-- base.html
|   `-- accounts/, workspace/, documents/, ai_assistant/, partials/
|-- static/
|   |-- css/styles.css
|   `-- js/ask.js
|-- docs/
|   |-- architecture.md, architecture-diagram.md
|   |-- database-erd.md, api-documentation.md, api-flow.md
|   |-- engineering-decisions.md, security.md, testing.md
|   `-- cost-and-scaling-analysis.md, requirements-checklist.md
|-- private_uploads/              # local files; gitignored
|-- .venv/                        # local environment; gitignored
|-- .env                          # local configuration; gitignored
|-- .env.example
|-- .gitignore
|-- db.sqlite3                    # local database; gitignored
|-- manage.py
|-- requirements.txt
|-- run.ps1
|-- README.md
`-- README.pdf
```

Apps also contain initialization/configuration files and, where applicable, admin registrations. `.git/`, `.claude/`, and `.vscode/` were present locally but are not application runtime components. Ignored local files need not exist in a fresh clone.

<!-- pagebreak -->

## 13. Known Limitations

- **Formats:** Only PDF/TXT; no OCR or DOCX support. Image-only PDFs fail extraction. Encrypted PDFs are readable only if an empty password authenticates them.
- **Retrieval:** Lexical matching with English stop words may miss paraphrases or non-English material. Search uses one selected document; TXT line references are approximate.
- **Answer reliability:** Mock mode returns excerpts. External grounding prompts and abstention do not formally verify facts or prevent all prompt injection. Sources are retrieved passages.
- **Performance:** Synchronous processing; TF-IDF is refitted per question. No task queue, persistent retrieval index, response cache, or streaming answers.
- **Database and deployment:** PostgreSQL lacks a bundled driver and full URL-option handling. SQLite has concurrency limits. WSGI/ASGI entry points exist, but complete production hosting is not supplied.
- **Product scope:** Single-owner workspaces. No team sharing, billing/subscriptions, email verification, password-reset routes, or multi-turn conversational memory in the inspected application.
- **Error boundaries:** Retrieval is outside the provider exception handler. JSON arrays or non-string questions can escape normal validation; some malformed provider response shapes are unhandled. Not every failure yields friendly JSON or a history entry.
- **Storage:** Initial file writing/metadata creation are outside the chunk transaction, so failures there may leave partial state. Deletion is best effort, and history retains document-derived text. No antivirus scanning or comprehensive binary-TXT detection is implemented.
- **Configuration and UI:** Numeric ranges lack full validation. The browser question limit stays at 1,000 even if the server limit changes. After a charged provider failure, the usage badge can remain stale until refresh.
- **Assets and secrets:** CDN access is needed for Bootstrap assets. The example secret must be replaced; the production guard rejects only a specific insecure prefix. Debug defaults to enabled for development.

## 14. GitHub Repository

**Repository:** https://github.com/raihaghani/DocuMind-AI

The local Git origin matches this URL. This guide describes the inspected working directory and does not assert remote synchronization.

Supporting architecture, database, API, engineering, security, testing, and scaling documentation is available in `docs/`. Source code remains authoritative where older documentation or proposed enhancements differ from current behavior.
