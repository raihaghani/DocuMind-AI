# Engineering Decisions

## Why Django

Django ships with exactly what this assignment needs: a secure auth system
(sessions, password hashing/validators), an ORM with migrations and
constraints, CSRF/XSS/SQL-injection protections, a template engine, and an
admin. That lets effort go into the document/AI logic rather than plumbing.

## Why Django Templates instead of React

The UI is form- and page-centric with a single asynchronous interaction (asking
a question). Server-rendered templates keep the stack small, make
authorization trivial to enforce per request, and are faster to build and
review. The one async flow is handled with a few dozen lines of vanilla JS
against a CSRF-protected JSON endpoint — no SPA toolchain required.

## Why SQLite for local development

SQLite is zero-config, file-based, and fully supported by the Django ORM, so a
reviewer can clone and `migrate` with nothing else installed. All schema
features used here (constraints, indexes, JSON field) work on SQLite.

## When PostgreSQL becomes appropriate

Move to PostgreSQL (set `DATABASE_URL`) when you need real write concurrency,
multiple app processes/servers, stronger row-level locking semantics for the
usage quota (`select_for_update` is a true row lock on PostgreSQL), larger data
volumes, or managed backups/replication. The code is DB-agnostic through the
ORM; no query changes are required.

## Why TF-IDF for the MVP

TF-IDF + cosine similarity (scikit-learn) gives genuine, explainable
information retrieval with **no external services, no API cost, and
deterministic behavior** — which also makes it unit-testable. It is more than
adequate for keyword-style questions over modest documents.

### Chunking parameters

Default **~1000 characters per chunk with ~150 characters of overlap**
(configurable via `CHUNK_SIZE` / `CHUNK_OVERLAP`). Rationale:

- ~1000 chars is large enough to keep a coherent idea together but small enough
  that a matched chunk is a precise citation.
- ~150 chars of overlap reduces the chance that an answer spanning a chunk
  boundary is lost.
- Very short documents are kept as a single chunk (no needless splitting).
- PDF chunks are tagged with their page number; TXT chunks with a line range.

## Limitations of TF-IDF

- **Lexical, not semantic.** It matches shared terms, so a question worded very
  differently from the source ("time off" vs "annual leave") may score low.
- **No reasoning or synthesis** across distant passages.
- The similarity threshold is a heuristic filter, **not** a guarantee that a
  retrieved passage actually answers the question, and **not** a hallucination
  detector.

## Why no vector database

A vector DB (and the embedding model behind it) adds an external dependency,
operational overhead, and usually cost — none of which the MVP needs. TF-IDF
covers the assignment's retrieval requirement locally. The migration path is
documented below.

## Migration path to embeddings / semantic search

1. Add an embedding step at upload time (store vectors per chunk).
2. Swap `retrieval.py` for an approximate-nearest-neighbor search (pgvector on
   PostgreSQL, or a dedicated vector store) while keeping the same
   `retrieve()` interface so views don't change.
3. Optionally keep TF-IDF as a hybrid lexical+semantic re-ranker.

Because retrieval is already a single, well-isolated function returning a
stable shape, this is a contained change.

## Why synchronous processing

Extraction and chunking run inside the upload request. For MVP-sized documents
this is simple and gives immediate feedback (the document is "ready" when the
response returns). It avoids introducing Celery/Redis, a broker, and worker
deployment.

## When background workers become necessary

Introduce Celery + Redis (or Django-Q/RQ) when documents get large or uploads
become slow enough to risk request timeouts, when you want retries/observability
on processing, or when embedding generation is added. The `documents/services`
pipeline is already a single function that a task could call unchanged.

## How the solution could scale

- PostgreSQL + connection pooling; multiple app workers behind a load balancer.
- S3-compatible object storage for `private_uploads/` (served via signed URLs
  or a streaming view).
- Background processing for extraction/embedding.
- A persistent retrieval index (vector store) instead of re-fitting TF-IDF per
  request.
- Response/retrieval caching and per-user rate limiting.
- Centralized logging, metrics, and error monitoring.
