# API Flow Diagram

Sequence for submitting a question via `POST /api/ask/`.

```mermaid
sequenceDiagram
    actor U as User (Browser)
    participant V as api_ask view
    participant Usg as usage.try_consume
    participant R as retrieval.retrieve
    participant P as ai_provider
    participant DB as Database

    U->>V: POST /api/ask/ {document_id, question} (session + CSRF)

    Note over V: 1. Authentication
    alt not authenticated
        V-->>U: 401 Authentication required
    end

    Note over V: 2. Validate question
    alt empty / too long / missing document
        V-->>U: 400 Invalid input
    end

    Note over V,DB: 3. Verify ownership & readiness
    V->>DB: Document.get(pk, owner=user)
    alt not found / not owned
        V-->>U: 404 Document not found
    else not ready
        V-->>U: 400 Not ready
    end

    Note over V,Usg: 4. Usage validation (atomic)
    V->>Usg: try_consume(user)
    Usg->>DB: SELECT ... FOR UPDATE; INSERT/UPDATE UsageRecord
    alt quota exhausted
        Usg-->>V: False
        V-->>U: 429 Daily limit reached (not charged)
    else quota available
        Usg-->>V: True (count += 1)
    end

    Note over V,R: 5. Retrieval (scoped to owned document)
    V->>DB: load DocumentChunk rows
    V->>R: retrieve(chunks, question)
    R-->>V: ranked chunks (>= RETRIEVAL_MIN_SCORE)

    Note over V,P: 6. Answer generation
    V->>P: generate(question, retrieved, document_name)
    alt provider timeout / failure
        P-->>V: raise ProviderTimeout / ProviderError
        V->>DB: save AIRequest(status=failed)
        V-->>U: 503 AI service unavailable
    else answered or abstained
        P-->>V: ProviderAnswer(answer, supported, sources)
    end

    Note over V,DB: 7. Persist history
    V->>DB: save AIRequest(status=success|unsupported, sources)

    Note over V: 8. Usage already accounted in step 4
    V-->>U: 200 {answer, sources, status, usage}
    U->>U: ask.js renders answer + sources + updated usage
```
