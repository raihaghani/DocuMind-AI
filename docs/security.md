# Security

## Authentication

- Django session authentication with secure password hashing (PBKDF2 by
  default).
- Registration enforces `AUTH_PASSWORD_VALIDATORS` (min length, common/numeric
  checks, user-attribute similarity) and prevents duplicate usernames/emails.
- Logout is POST-only and CSRF-protected.

## Authorization & object isolation

- Every private view uses `@login_required`; the JSON API returns `401` when
  unauthenticated.
- Ownership is enforced **in the database query**, e.g.
  `get_object_or_404(Document, pk=pk, owner=request.user)`. Accessing another
  user's document/history returns **404**, so existence is not revealed
  (defense against Insecure Direct Object References).
- `DocumentChunk` carries a denormalized `owner`; retrieval only ever loads
  chunks of a document already verified to belong to the requester.
- These rules are covered by automated authorization tests (cross-user view,
  download, delete, query, and history access).

## Private file storage

- Files are stored in `private_uploads/user_<id>/<uuid>.<ext>`, **outside** the
  static/media web root, and are never exposed via a public URL.
- Downloads go through an authenticated, ownership-checked view that streams the
  file and sets `Content-Disposition: attachment`.

## CSRF

- `CsrfViewMiddleware` is enabled. All forms include `{% csrf_token %}`.
- The JSON `ask` endpoint is **not** CSRF-exempt; `ask.js` sends the
  `X-CSRFToken` header read from the cookie.

## Upload validation

- Extension allow-list (`pdf`, `txt`); browser MIME type is not trusted.
- Size limit (`MAX_UPLOAD_SIZE_MB`, default 10 MB) and empty-file rejection.
- Actual format is validated by attempting real extraction (PyMuPDF for PDFs);
  corrupted or text-less files are marked `failed` with a safe message rather
  than crashing.
- Stored filenames are **server-generated UUIDs** — user-supplied path
  components are never used on disk (path-traversal defense). The download view
  additionally verifies the resolved path stays within the storage root.

## Prompt injection

- Uploaded document text is treated strictly as untrusted **data**, never as
  instructions.
- The real provider's system prompt explicitly states the context is untrusted
  source material and that any instructions embedded in it must be ignored, and
  requires the model to answer only from the provided context or abstain.

## Secrets & configuration

- All secrets/config come from environment variables (`.env` in development,
  loaded via `python-dotenv`). Nothing is hardcoded.
- `.env` and `private_uploads/` are gitignored. `DEBUG=False` requires a
  non-placeholder `DJANGO_SECRET_KEY` (enforced in settings).

## Error handling & disclosure

- Users never see raw tracebacks; views return friendly messages and the JSON
  API uses appropriate status codes (400/401/404/429/503).
- Technical errors are logged server-side (via the `documind` logger) without
  logging document contents or secrets.

## SQL injection & XSS

- All data access goes through the Django ORM (no raw SQL), so queries are
  parameterized.
- Django templates auto-escape output; the async answer renderer in `ask.js`
  uses `textContent`/an escape helper rather than raw `innerHTML` for
  user/document-derived strings.

## Production hardening (applied automatically when `DEBUG=False`)

- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
- HSTS (`SECURE_HSTS_SECONDS` with subdomains + preload).
- `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS = DENY`,
  `SECURE_PROXY_SSL_HEADER` for deployment behind a TLS-terminating proxy.

### Operational checklist for production

- [ ] `DJANGO_DEBUG=False`
- [ ] Strong, unique `DJANGO_SECRET_KEY`
- [ ] Correct `DJANGO_ALLOWED_HOSTS`
- [ ] HTTPS enforced end-to-end
- [ ] PostgreSQL with least-privilege credentials
- [ ] `private_uploads/` on durable storage, backed up, off the web root
- [ ] Database + uploads backup schedule
- [ ] Centralized logging and error monitoring
