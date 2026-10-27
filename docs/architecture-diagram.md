# Architecture Diagram

## Mermaid

```mermaid
flowchart TD
    Browser["User Browser<br/>(Django Templates + Bootstrap + ask.js)"]

    subgraph Django["Django Application (config.urls)"]
        Auth["accounts<br/>Authentication"]
        WS["workspace<br/>Dashboard / Workspace"]
        Docs["documents<br/>Upload / Download / Delete"]
        AI["ai_assistant<br/>Ask / History / JSON API"]

        subgraph Services["ai_assistant.services"]
            Extract["extraction.py<br/>(PyMuPDF / stdlib)"]
            Chunk["chunking.py"]
            Retrieve["retrieval.py<br/>(TF-IDF + cosine)"]
            Provider["ai_provider.py<br/>(mock / OpenAI)"]
            Usage["usage.py<br/>(atomic quota)"]
        end
    end

    DB[("Database<br/>SQLite / PostgreSQL")]
    Storage[["Private Storage<br/>private_uploads/"]]
    ExtAI{{"External AI API<br/>(optional, OpenAI-compatible)"}}

    Browser -->|HTTPS| Auth
    Browser -->|HTTPS| WS
    Browser -->|HTTPS| Docs
    Browser -->|JSON /api/ask/| AI

    Auth --> DB
    WS --> DB

    Docs --> Extract
    Docs --> Chunk
    Docs --> Storage
    Docs --> DB

    AI --> Usage
    AI --> Retrieve
    AI --> Provider
    AI --> DB

    Retrieve --> DB
    Usage --> DB
    Provider -. "only when AI_PROVIDER=openai" .-> ExtAI
```

## Lucidchart-compatible specification

Recreate the diagram with these nodes and directed edges.

**Nodes**

| ID       | Label                                   | Shape          |
| -------- | --------------------------------------- | -------------- |
| browser  | User Browser                            | Rounded rect   |
| auth     | accounts (Authentication)               | Rectangle      |
| ws       | workspace (Dashboard)                   | Rectangle      |
| docs     | documents (Upload/Download/Delete)      | Rectangle      |
| ai       | ai_assistant (Ask/History/API)          | Rectangle      |
| extract  | extraction.py (PyMuPDF/stdlib)          | Rectangle      |
| chunk    | chunking.py                             | Rectangle      |
| retrieve | retrieval.py (TF-IDF + cosine)          | Rectangle      |
| provider | ai_provider.py (mock/OpenAI)            | Rectangle      |
| usage    | usage.py (atomic quota)                 | Rectangle      |
| db       | Database (SQLite/PostgreSQL)            | Cylinder       |
| storage  | Private Storage (private_uploads/)      | Document/Store |
| extai    | External AI API (optional)             | Hexagon        |

**Edges (source → target, label)**

```
browser -> auth        (HTTPS)
browser -> ws          (HTTPS)
browser -> docs        (HTTPS, multipart upload)
browser -> ai          (JSON /api/ask/, CSRF token)
auth -> db
ws -> db               (live stats)
docs -> extract
docs -> chunk
docs -> storage        (write/read private files)
docs -> db
ai -> usage
ai -> retrieve
ai -> provider
ai -> db               (save AIRequest)
retrieve -> db         (load chunks)
usage -> db            (UsageRecord, atomic)
provider -> extai      (dashed; only when AI_PROVIDER=openai)
```

**Groupings (containers):** put `auth, ws, docs, ai` inside a "Django
Application" container, and `extract, chunk, retrieve, provider, usage` inside
an "ai_assistant.services" sub-container.
