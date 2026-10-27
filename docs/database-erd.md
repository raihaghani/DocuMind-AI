# Database ERD

This ERD matches the Django models in `workspace/models.py`,
`documents/models.py`, and `ai_assistant/models.py`.

```mermaid
erDiagram
    USER ||--|| WORKSPACE : "has one"
    USER ||--o{ DOCUMENT : "owns"
    WORKSPACE ||--o{ DOCUMENT : "contains"
    USER ||--o{ DOCUMENTCHUNK : "owns"
    DOCUMENT ||--o{ DOCUMENTCHUNK : "split into"
    USER ||--o{ AIREQUEST : "makes"
    DOCUMENT ||--o{ AIREQUEST : "about (SET_NULL)"
    USER ||--o{ USAGERECORD : "accrues"

    USER {
        int id PK
        string username UK
        string email
        string password "hashed"
        datetime date_joined
    }

    WORKSPACE {
        int id PK
        int owner_id FK "OneToOne -> USER"
        string name
        datetime created_at
    }

    DOCUMENT {
        int id PK
        int owner_id FK "-> USER"
        int workspace_id FK "-> WORKSPACE"
        string original_filename
        string stored_filename "server-generated"
        string storage_path "relative to PRIVATE_STORAGE_ROOT"
        string file_type "pdf|txt"
        int file_size
        datetime uploaded_at
        string status "processing|ready|failed"
        int char_count
        int page_count
        int chunk_count
        text error_message
    }

    DOCUMENTCHUNK {
        int id PK
        int document_id FK "-> DOCUMENT (CASCADE)"
        int owner_id FK "-> USER (denormalized)"
        int seq "0-based"
        text text
        int page_number "nullable (PDF)"
        string reference "e.g. Page 3 / Lines 10-20"
    }

    AIREQUEST {
        int id PK
        int user_id FK "-> USER"
        int document_id FK "-> DOCUMENT, nullable SET_NULL"
        string document_name "snapshot"
        text question
        text answer
        string status "success|unsupported|failed"
        string provider_mode "mock|openai"
        json sources
        string error_detail
        datetime created_at
    }

    USAGERECORD {
        int id PK
        int user_id FK "-> USER"
        date date
        int count
    }
```

## Keys, constraints & indexes

- **WORKSPACE.owner** — `OneToOne` to `USER` (`CASCADE`): one workspace per user.
- **DOCUMENT** — FKs to `USER` and `WORKSPACE` (`CASCADE`). Indexes on
  `(owner, -uploaded_at)` and `status`.
- **DOCUMENTCHUNK** — FK to `DOCUMENT` (`CASCADE`) and denormalized FK to
  `USER`. `unique_together (document, seq)`; indexes on `(document, seq)` and
  `owner`.
- **AIREQUEST** — FK to `USER` (`CASCADE`); FK to `DOCUMENT` is
  **`SET_NULL`** so history survives document deletion (with `document_name`
  preserved). Indexes on `(user, -created_at)` and `status`.
- **USAGERECORD** — `UniqueConstraint(user, date)` prevents duplicate daily
  records; index on `(user, date)`.

## Deletion behavior

| Action              | Effect                                                        |
| ------------------- | ------------------------------------------------------------- |
| Delete User         | Cascades to Workspace, Documents, Chunks, AIRequests, Usage   |
| Delete Workspace    | Cascades to its Documents (and their Chunks)                  |
| Delete Document     | Cascades to Chunks; sets `AIRequest.document = NULL` (history kept); stored file removed |
