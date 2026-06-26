"""
searcher.py — ChromaDB query + similarity score conversion for semantic-engine.

RESEARCH Pitfall 1 (HIGH IMPACT): ChromaDB returns cosine DISTANCE (0=identical,
higher=more different). Similarity = 1 - distance. Filter on score < threshold,
NOT on dist > threshold.
"""
import logging

import ollama

from config import OLLAMA_EMBED_MODEL, OLLAMA_URL

logger = logging.getLogger(__name__)

# ponytail: module-level singleton; tests inject via monkeypatch.setattr(searcher, "_ollama", ...)
_ollama = ollama.Client(host=OLLAMA_URL)


def embed_query(text: str, ollama_client=None) -> list:
    """Embed a query string. Uses ollama_client if provided (for tests), else _ollama."""
    client = ollama_client if ollama_client is not None else _ollama
    response = client.embed(model=OLLAMA_EMBED_MODEL, input=text)
    return response.embeddings[0]  # plural — not deprecated .embedding singular (Pitfall 4)


def search(
    collection,
    query: str,
    ollama_client=None,
    n_results: int = 10,
    threshold: float = 0.3,
) -> list:
    """
    Query ChromaDB and return results with similarity scores above threshold.

    score = round(1.0 - distance, 4)  — RESEARCH Pitfall 1: distance ≠ similarity
    Filters on score < threshold (not on raw distance).
    ChromaDB returns results ordered by distance ascending (most similar first),
    so output list is already ranked by score descending.
    """
    query_vec = embed_query(query, ollama_client)
    raw = collection.query(
        query_embeddings=[query_vec],
        n_results=n_results,
        include=["distances", "metadatas", "documents"],
    )

    output = []
    for dist, meta in zip(raw["distances"][0], raw["metadatas"][0]):
        score = round(1.0 - dist, 4)
        if score < threshold:  # D-07: drop low-similarity results
            continue
        output.append({
            "ioc_type": meta["ioc_type"],
            "value": meta["value"],
            "score": score,
            "opencti_url": meta["opencti_url"],
            "embedded_text": meta["embedded_text"],  # D-08
        })
    return output
