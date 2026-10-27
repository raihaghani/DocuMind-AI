# API Documentation

DocuMind AI is primarily server-rendered. Most routes return HTML; two routes
(`/api/ask/`, `/api/usage/`) return JSON. All private routes require an
authenticated session. HTML routes redirect unauthenticated users to the login
page; JSON routes return `401`.

CSRF protection is enabled everywhere. The JSON API expects the `X-CSRFToken`
header (the browser `ask.js` reads it from the `csrftoken` cookie).

## Route summary

| Method     | Path                        | Auth | Type | Purpose              |
| ---------- | --------------------------- | ---- | ---- | -------------------- |
| GET        | `/`                         | no   | HTML | Landing page         |
| GET/POST   | `/register/`                | no   | HTML | Registration         |
| GET/POST   | `/login/`                   | no   | HTML | Login                |
| POST       | `/logout/`                  | yes  | HTML | Logout               |
| GET        | `/dashboard/`               | yes  | HTML | Workspace dashboard  |
| GET        | `/account/`                 | yes  | HTML | Account overview     |
| GET        | `/documents/`               | yes  | HTML | List documents       |
| GET/POST   | `/documents/upload/`        | yes  | HTML | Upload document      |
| GET        | `/documents/{id}/`          | yes  | HTML | Document details     |
| GET        | `/documents/{id}/download/` | yes  | FILE | Secure download      |
| POST       | `/documents/{id}/delete/`   | yes  | HTML | Delete document      |
| GET        | `/ask/`                     | yes  | HTML | Question interface   |
| POST       | `/api/ask/`                 | yes  | JSON | Submit a question    |
| GET        | `/history/`                 | yes  | HTML | Question history     |
| GET        | `/history/{id}/`            | yes  | HTML | History detail       |
| GET        | `/api/usage/`               | yes  | JSON | Current usage        |

## JSON endpoints

### POST `/api/ask/`

Submit a question about one of your processed documents.

**Request headers:** `Content-Type: application/json`, `X-CSRFToken: <token>`.
(Form-encoded bodies are also accepted.)

**Request body**

```json
{ "document_id": 12, "question": "How many paid leave days do employees get?" }
```

**Success response — 200**

```json
{
  "id": 48,
  "status": "success",
  "answer": "Based on the most relevant passages found in \"policy.pdf\": ...",
  "supported": true,
  "is_mock": true,
  "provider": "mock",
  "sources": [
    { "label": "Page 3", "page": 3, "snippet": "Employees receive 20 days ...", "score": 0.41 }
  ],
  "usage": { "used": 3, "limit": 10, "remaining": 7, "percent": 30, "at_limit": false }
}
```

**Insufficient evidence — 200** (`status: "unsupported"`)

```json
{
  "status": "unsupported",
  "answer": "I couldn't find sufficient information in the uploaded document to answer this question.",
  "supported": false,
  "sources": [],
  "usage": { "used": 4, "limit": 10, "remaining": 6, "percent": 40, "at_limit": false }
}
```

**Error responses**

| Status | When                                            | Body                                   |
| ------ | ----------------------------------------------- | -------------------------------------- |
| 400    | Empty / too-long question, missing doc, bad JSON | `{"error": "...", "status": 400}`     |
| 401    | Not authenticated                               | `{"error": "Authentication required.", "status": 401}` |
| 404    | Document not found **or not owned by the user**  | `{"error": "Document not found.", "status": 404}` |
| 429    | Daily quota already exhausted (not charged)      | `{"error": "Daily question limit reached...", "status": 429}` |
| 503    | AI provider timeout/failure (request saved as failed) | `{"error": "The AI service ...", "status": 503}` |

**Example (curl)**

```bash
curl -X POST http://127.0.0.1:8000/api/ask/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -b cookies.txt \
  -d '{"document_id": 12, "question": "How many paid leave days?"}'
```

### GET `/api/usage/`

Returns the authenticated user's usage for today.

**Response — 200**

```json
{ "used": 3, "limit": 10, "remaining": 7, "percent": 30, "at_limit": false }
```

Returns `401` if not authenticated.

## Notes on HTML routes

- `/documents/{id}/`, `/download/`, `/delete/`, `/history/{id}/` all scope the
  lookup to `owner=request.user`, returning **404** for resources owned by
  another user (existence is not disclosed).
- `/documents/{id}/download/` streams the original file as an attachment after
  verifying ownership and that the resolved path is inside the private storage
  root.
- `/logout/` and `/documents/{id}/delete/` are **POST-only** (CSRF-protected).
