"""
semantic_search.py
===================
Lightweight, dependency-light semantic search over document text.

Per project decision: NEVER use ChromaDB (breaks on Streamlit Cloud due to a
Python 3.14 dependency conflict). Instead we build a TF-IDF vector space
with scikit-learn and do cosine similarity with NumPy. This is:
    - Pure Python/NumPy/sklearn -> no native build steps, no server,
      no extra Streamlit Cloud packages.txt entries needed.
    - Good enough for single-document / small-corpus semantic search,
      which is the actual use case here (searching within one contract,
      or across a handful of a user's uploaded documents).

Two entry points:
    - SemanticIndex: build a searchable index over chunks of ONE document
      (used by the "Semantic Search" and RAG Q&A tabs).
    - search_documents_corpus: search across MULTIPLE documents' raw text
      (used for "Multi-Job"/cross-document style matching in app.py).
"""

import re
from dataclasses import dataclass
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks (by characters) along sentence-ish boundaries."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # try to break on a sentence boundary near the end
        window = text[start:end]
        last_period = window.rfind(". ")
        if last_period > chunk_size * 0.5:
            end = start + last_period + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - overlap
    return [c for c in chunks if c]


@dataclass
class SearchResult:
    chunk: str
    score: float
    chunk_index: int


class SemanticIndex:
    """A small in-memory TF-IDF index over the chunks of a single document."""

    def __init__(self, text: str, chunk_size: int = 800, overlap: int = 150):
        self.chunks = chunk_text(text, chunk_size, overlap)
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        if self.chunks:
            self.matrix = self.vectorizer.fit_transform(self.chunks)
        else:
            self.matrix = None

    def is_empty(self) -> bool:
        return not self.chunks

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        if self.is_empty() or not query.strip():
            return []
        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.matrix).flatten()
        top_indices = np.argsort(sims)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(sims[idx])
            if score > 0:
                results.append(SearchResult(chunk=self.chunks[idx], score=score, chunk_index=int(idx)))
        return results

    def get_context_for_rag(self, query: str, top_k: int = 3, max_chars: int = 2500) -> str:
        """Retrieve the most relevant chunks and join them for use as RAG context in a prompt."""
        results = self.search(query, top_k=top_k)
        context = "\n\n---\n\n".join(r.chunk for r in results)
        return context[:max_chars]


def search_documents_corpus(documents: List[dict], query: str, top_k: int = 5) -> List[dict]:
    """
    Search across multiple documents (each: {'id', 'filename', 'text'}) and return
    the best-matching documents ranked by cosine similarity of the whole doc to the query.
    Used for cross-document / multi-contract search scenarios.
    """
    valid_docs = [d for d in documents if d.get("text", "").strip()]
    if not valid_docs or not query.strip():
        return []

    corpus = [d["text"] for d in valid_docs]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(corpus)
    query_vec = vectorizer.transform([query])
    sims = cosine_similarity(query_vec, matrix).flatten()

    ranked = sorted(zip(valid_docs, sims), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        {"id": d["id"], "filename": d["filename"], "score": float(score)}
        for d, score in ranked if score > 0
    ]


def compare_clauses(text_a: str, text_b: str, top_k: int = 5) -> List[dict]:
    """
    Chunk two contracts and, for each chunk in A, find its closest-matching chunk in B.
    Used for the 'AI Clause Comparison' / 'Version Comparison' bonus feature (the
    numeric similarity is computed here; ai_analyzer.py adds the LLM-explained diff).
    """
    chunks_a = chunk_text(text_a, chunk_size=500, overlap=50)
    chunks_b = chunk_text(text_b, chunk_size=500, overlap=50)
    if not chunks_a or not chunks_b:
        return []

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    all_chunks = chunks_a + chunks_b
    matrix = vectorizer.fit_transform(all_chunks)
    matrix_a = matrix[: len(chunks_a)]
    matrix_b = matrix[len(chunks_a):]

    sims = cosine_similarity(matrix_a, matrix_b)
    comparisons = []
    for i, chunk_a in enumerate(chunks_a[:top_k]):
        best_j = int(np.argmax(sims[i]))
        comparisons.append({
            "clause_a": chunk_a,
            "clause_b": chunks_b[best_j],
            "similarity": float(sims[i][best_j]),
        })
    return comparisons
