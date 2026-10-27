# Testing

## Test strategy

Tests exercise the real pipeline end to end using Django's `TestCase` (each test
runs in a transaction and is rolled back). File-based tests write to a
temporary `PRIVATE_STORAGE_ROOT` via `override_settings` and clean it up, so no
real uploads directory is touched. The AI path is tested with the deterministic
**mock provider** and with the real provider's HTTP call mocked — **no paid API
is ever called**.

## Test categories & files

| Area | File | What it covers |
| ---- | ---- | -------------- |
| Authentication | `accounts/tests.py` | register, duplicate username, weak password, login, logout (POST-only), invalid login, protected-page redirects |
| Workspace / dashboard | `workspace/tests.py` | auto-created workspace, idempotent get-or-create, live dashboard stats |
| Document processing | `documents/tests.py` | valid PDF/TXT, invalid type, empty, oversized, corrupted PDF, no-text PDF, page-number tracking |
| Document authorization | `documents/tests.py` | cross-user view/download/delete blocked (404), owner can download/delete, file + chunks removed |
| Chunking | `ai_assistant/tests.py` | short text single chunk, long text split with contiguous sequence |
| Retrieval | `ai_assistant/tests.py` | relevant chunk retrieved, empty question, no chunks, threshold filters unrelated questions |
| AI providers | `ai_assistant/tests.py` | mock is default, mock grounded + abstain, real provider missing-credentials error, abstain-token handling |
| Usage limits | `ai_assistant/tests.py` | quota starts full, counts, enforces limit, per-user isolation, daily reset by date |
| Ask API | `ai_assistant/tests.py` | 401 unauth, success saves history + counts, empty rejected (not charged), unsupported saved, cross-user query 404 (not charged), 429 at limit, 503 on timeout (saved failed), history private, history retained after document deletion |

## How to run

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py check
python manage.py test
```

Run a single app or test:

```powershell
python manage.py test ai_assistant
python manage.py test ai_assistant.tests.AskApiTests.test_quota_enforced_via_api
```

## Results

### Latest recorded run (2026-10-27, Python 3.12.10, Django 5.2.18)

```text
$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py test
...
----------------------------------------------------------------------
Ran 45 tests in 341.162s

OK
```

- **45 tests, all passing**, exit code 0.
- The run is slow (~5–6 min) because several tests generate real PDFs with
  PyMuPDF and fit scikit-learn TF-IDF models; this is expected, not a failure.
- `INFO documind: Document ... processing failed: ...` and
  `WARNING django.request: Not Found: /documents/1/...` lines in the output are
  **expected** — they are the negative-path tests (corrupted/no-text PDFs and
  cross-user 404 authorization checks) asserting the correct behavior.

## Important edge cases covered

- Corrupted / text-less PDFs are marked `failed` with a safe message (no crash,
  no orphaned state).
- Unsupported questions return the abstain message and are saved as
  `unsupported`.
- Provider timeout/failure returns `503` and is saved as `failed` (quota was
  consumed because the request was accepted for processing).
- Unauthorized and invalid requests never consume quota.
- Deleting a document keeps its question history (`document` → NULL, name
  snapshotted).

## Manual testing checklist

1. Register a new user → redirected to dashboard; workspace exists.
2. Log out (button) → redirected to login; dashboard now requires login.
3. Log in with wrong password → error shown.
4. Upload a text PDF → status becomes **Ready**, pages/chunks shown.
5. Upload a `.docx` → rejected with "Unsupported file type".
6. Upload a blank/scanned PDF → shows **Failed** with a clear message.
7. Ask a question answerable from the document → grounded answer + sources +
   usage decrements.
8. Ask an unrelated question → "couldn't find sufficient information".
9. Exhaust the daily limit → further asks show the limit message (429).
10. As a second user, try opening user 1's document/history URL by id → 404.
11. Download your own document → file downloads; delete it → history remains.
