"""Document retrieval using scikit-learn TF-IDF + cosine similarity.

Retrieval is scoped to a single, ownership-verified document. The caller is
responsible for passing only chunks the requesting user is authorized to see.
The service is deterministic (no randomness) so it is fully testable without
external services.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass
class RetrievedChunk:
    seq: int
    text: str
    page_number: int | None
    reference: str
    source_label: str
    score: float


def retrieve(chunks, question: str, top_k: int | None = None):
    """Rank `chunks` against `question` by TF-IDF cosine similarity.

    `chunks` is an iterable of objects exposing .seq, .text, .page_number,
    .reference and .source_label (e.g. DocumentChunk instances).

    Returns a list of RetrievedChunk ordered by descending score. Chunks below
    settings.RETRIEVAL_MIN_SCORE are excluded. Returns [] when retrieval is not
    possible (no chunks, empty question, or no shared vocabulary).
    """
    top_k = top_k or settings.RETRIEVAL_TOP_K
    min_score = settings.RETRIEVAL_MIN_SCORE

    chunk_list = list(chunks)
    question = (question or "").strip()
    if not chunk_list or not question:
        return []

    # Imported lazily so the rest of the app loads even if sklearn is absent.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    corpus = [c.text for c in chunk_list]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
    )
    try:
        doc_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        # Corpus had only stop words / empty vocabulary.
        return []

    try:
        query_vec = vectorizer.transform([question])
    except ValueError:
        return []

    if query_vec.nnz == 0:
        # Question shares no vocabulary with the document.
        return []

    scores = cosine_similarity(query_vec, doc_matrix)[0]

    ranked = sorted(
        range(len(chunk_list)),
        key=lambda i: scores[i],
        reverse=True,
    )

    results: list[RetrievedChunk] = []
    for idx in ranked[:top_k]:
        score = float(scores[idx])
        if score < min_score:
            continue
        chunk = chunk_list[idx]
        results.append(
            RetrievedChunk(
                seq=chunk.seq,
                text=chunk.text,
                page_number=chunk.page_number,
                reference=chunk.reference,
                source_label=chunk.source_label,
                score=round(score, 4),
            )
        )
    return results
