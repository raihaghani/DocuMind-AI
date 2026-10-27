# DocuMind AI

A document-based AI SaaS workspace. Authenticated users upload PDF/TXT
documents, ask natural-language questions about them, and receive
**document-grounded** answers with source references — plus per-user question
history and daily usage limits.

Built for the FalconXoft technical assignment.

---

## 1. Overview

DocuMind AI turns a user's private documents into a question-answering
knowledge base. Each user gets an isolated workspace. Uploaded files are stored
privately (never served from a public URL), text is extracted and chunked,
and questions are answered using **TF-IDF retrieval** over the selected
document followed by an **answer provider** (a built-in mock provider by
default, or a configurable real AI API). Answers cite the passages they came
from, and the system abstains when the document doesn't contain the answer.

## 2. Features

- Email/username registration, session login, POST-only logout
- Private per-user workspace with a live statistics dashboard
- Secure PDF/TXT upload with validation (type, size, emptiness, corruption,
  no-text detection)
- Private file storage + authenticated, ownership-checked downloads
- PyMuPDF text extraction with page-number tracking
- Deterministic text chunking with overlap
- Scikit-learn TF-IDF + cosine-similarity retrieval
- Grounded answering with source citations and an insufficient-evidence path
- Configurable AI provider: honest **mock** (default, no credentials) or
  **OpenAI-compatible** real API
- Persistent request history (successful / unsupported / failed)
- Atomic per-user daily usage limits (default 10/day)
- Strict cross-user isolation enforced at the query level
- CSRF-protected JSON API for asynchronous question submission
- Automated test suite (Django `TestCase`)

## 3. Technology stack

| Layer            | Technology                                   |
| ---------------- | -------------------------------------------- |
| Language         | Python 3.12                                  |
| Framework        | Django 5.2                                   |
| Frontend         | Django Templates + Bootstrap 5 + vanilla JS  |
| Dev database     | SQLite                                       |
| Prod database    | PostgreSQL (via `DATABASE_URL`)              |
| PDF extraction   | PyMuPDF                                       |
| Retrieval        | scikit-learn (TF-IDF, cosine similarity)     |
| AI provider      | Mock (default) or OpenAI-compatible HTTP API |
| Config / secrets | Environment variables (`python-dotenv`)      |

> **Note on Python version:** scikit-learn and PyMuPDF ship prebuilt wheels for
> Python 3.12. The project was developed and tested on 3.12; newer interpreters
> may require building those packages from source.

## 4. Architecture overview

```
Browser ──> Django (config.urls)
            ├─ accounts     : registration / login / logout
            ├─ workspace    : Workspace model + dashboard (live stats)
            ├─ documents    : upload, storage, extraction, chunking, download
            └─ ai_assistant : retrieval, AI provider, usage, history, JSON API
                              services/ { extraction, chunking, retrieval,
                                          ai_provider, usage }
Storage: private_uploads/ (outside the web root)
DB     : SQLite (dev) / PostgreSQL (prod)
```

Full details in [docs/architecture.md](docs/architecture.md) and the diagrams
under [docs/](docs/).

## 5. Folder structure

```
documind-ai/
├── config/          # settings, urls, wsgi/asgi
├── accounts/        # authentication
├── workspace/       # Workspace model + dashboard
├── documents/       # Document & DocumentChunk, upload/download/delete
├── ai_assistant/    # AIRequest & UsageRecord, services, ask/history/API
│   └── services/    # extraction, chunking, retrieval, ai_provider, usage
├── templates/       # base + per-app templates
├── static/          # css + js
├── private_uploads/ # private document storage (gitignored)
├── docs/            # engineering documentation
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

## 6. Setup (Windows PowerShell)

```powershell
# From the project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Create your local environment file
Copy-Item .env.example .env
# (optional) generate a secret key:
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# paste the value into DJANGO_SECRET_KEY in .env

python manage.py migrate
python manage.py createsuperuser   # optional, for the admin
python manage.py runserver
```

Then open http://127.0.0.1:8000/.

> If `python` resolves to a version without prebuilt wheels, create the venv
> with 3.12 explicitly: `py -3.12 -m venv .venv`.

## 7. Environment configuration

Copy `.env.example` to `.env` and adjust. Key variables:

| Variable               | Default            | Purpose                                 |
| ---------------------- | ------------------ | --------------------------------------- |
| `DJANGO_SECRET_KEY`    | dev placeholder    | Required (non-placeholder) in prod      |
| `DJANGO_DEBUG`         | `True`             | Set `False` in production               |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated hosts                |
| `DATABASE_URL`         | empty (SQLite)     | `postgres://…` for PostgreSQL           |
| `DJANGO_TIME_ZONE`     | `UTC`              | Used for daily quota resets             |
| `AI_PROVIDER`          | `mock`             | `mock` or `openai`                      |
| `AI_API_KEY`           | empty              | Required when `AI_PROVIDER=openai`      |
| `AI_MODEL`             | `gpt-4o-mini`      | Model identifier for the real provider  |
| `MAX_UPLOAD_SIZE_MB`   | `10`               | Upload size ceiling                     |
| `DAILY_QUESTION_LIMIT` | `10`               | AI questions per user per day           |
| `RETRIEVAL_MIN_SCORE`  | `0.05`             | Min cosine score to count as evidence   |

## 8. Database setup

The default SQLite database is created by `python manage.py migrate`. For
PostgreSQL, set `DATABASE_URL` and run `migrate` again. See
[docs/database-erd.md](docs/database-erd.md).

## 9. Running the application

```powershell
python manage.py runserver
```

## 10. Running tests

```powershell
python manage.py check
python manage.py test
```

Test strategy, categories, and the latest recorded results are in
[docs/testing.md](docs/testing.md).

## 11. AI provider configuration

- **Mock (default):** no credentials needed. Returns an *extractive* answer
  built from the top retrieved passages and is clearly labelled in the UI as a
  mock response. It never pretends to perform AI reasoning. Deterministic, so
  tests run without any paid API.
- **Real (OpenAI-compatible):** set `AI_PROVIDER=openai` and `AI_API_KEY`. The
  provider sends the question plus retrieved context to a chat-completions
  endpoint with a strict grounding prompt and an explicit abstain instruction.

## 12. Daily usage-limit policy

- Default **10 questions per user per day** (`DAILY_QUESTION_LIMIT`).
- A question consumes quota **once it is accepted for processing** (valid input,
  owned & ready document, quota available).
- Not charged: invalid form submissions, unauthorized document access, and
  requests rejected because the quota is already exhausted.
- Charged: accepted requests whose provider later fails or returns
  "unsupported" (the work was attempted).
- Enforcement is server-side and atomic (`select_for_update`), so concurrent
  requests cannot exceed the limit. Daily boundary uses `timezone.localdate()`
  with `DJANGO_TIME_ZONE` (default UTC).

## 13. Documentation

- [Architecture](docs/architecture.md)
- [Architecture diagram](docs/architecture-diagram.md)
- [Database ERD](docs/database-erd.md)
- [API documentation](docs/api-documentation.md)
- [API flow diagram](docs/api-flow.md)
- [Engineering decisions](docs/engineering-decisions.md)
- [Security](docs/security.md)
- [Testing](docs/testing.md)
- [Cost & scaling analysis](docs/cost-and-scaling-analysis.md)
- [Requirements checklist](docs/requirements-checklist.md)

## 14. Known limitations

- **Lexical retrieval only.** TF-IDF matches wording, not meaning; questions
  phrased very differently from the source may score below threshold. Migration
  to embeddings/semantic search is described in the engineering decisions.
- **No OCR.** Scanned/image-only PDFs have no extractable text and are rejected
  with a clear message.
- **Synchronous processing.** Extraction/chunking run in the request cycle;
  very large documents will make uploads slower. Background workers are a
  documented future enhancement.
- **Retrieval threshold is heuristic**, not a hallucination guarantee.

## 15. Deployment considerations

See [docs/security.md](docs/security.md) (production hardening) and
[docs/cost-and-scaling-analysis.md](docs/cost-and-scaling-analysis.md). In
production: set `DJANGO_DEBUG=False`, a strong `DJANGO_SECRET_KEY`, real
`DJANGO_ALLOWED_HOSTS`, serve over HTTPS (secure cookies + HSTS are enabled
automatically when `DEBUG=False`), use PostgreSQL, keep `private_uploads/` off
the public web root, and back up the database and uploads.
