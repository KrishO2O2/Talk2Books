"""
backend/rag_chain.py
Talk2Books — Phase 3
Day 1: embed_query()
Day 2: retrieve_chunks() with Qdrant search
Day 3: language detection + payload filtering + metadata fix
"""

import logging
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from langdetect import detect, LangDetectException

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("ttb.rag_chain")

# ── Config ─────────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
QDRANT_URL      = "http://localhost:6333"
COLLECTION_NAME = "ttb_documents"
TOP_K           = 3

# ── Module-level singletons ────────────────────────────────────────────────────
# Loaded once when the module is first imported — not on every function call
embedder = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

qdrant = QdrantClient(url=QDRANT_URL)


# ── Day 1: Query Embedding ─────────────────────────────────────────────────────

def embed_query(question: str) -> list[float]:
    """
    Convert a user's question into a 768-dimensional vector.
    Uses the same model as ingest.py — critical for Qdrant search to work.
    """
    return embedder.embed_query(question)


# ── Day 3: Language Detection ──────────────────────────────────────────────────

def detect_query_language(question: str) -> str:
    """
    Detect the language of the user's question.
    Returns ISO 639-1 code: 'en', 'hi', 'pa', etc.
    Returns 'unknown' if detection fails (e.g. text too short).
    """
    try:
        return detect(question)
    except LangDetectException:
        log.warning("Language detection failed for query — defaulting to 'unknown'.")
        return "unknown"


# ── Day 2 + 3: Retrieval with Language Filter ──────────────────────────────────

def retrieve_chunks(question: str, filter_language: bool = True) -> list[dict]:
    """
    Embed the question and search Qdrant for the top-k most similar chunks.

    Args:
        question:        The user's question string.
        filter_language: If True, restrict results to chunks whose language
                         matches the detected query language.
                         Falls back to unfiltered search if no matches found.

    Returns:
        List of dicts with keys: text, score, source, language, file_name.
    """
    query_vector = embed_query(question)
    lang = detect_query_language(question)
    log.info(f"Query language detected: '{lang}'")

    # ── Build language filter ──────────────────────────────────────────────────
    # LangChain's QdrantVectorStore nests metadata under a 'metadata' key.
    # Qdrant uses dot notation to filter on nested fields: "metadata.language"
    query_filter = None
    if filter_language and lang != "unknown":
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.language",
                    match=MatchValue(value=lang),
                )
            ]
        )
        log.info(f"Applying language filter: metadata.language = '{lang}'")

    # ── Primary search ─────────────────────────────────────────────────────────
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=TOP_K,
        with_payload=True,
        query_filter=query_filter,
    ).points

    # ── Fallback: retry without language filter ────────────────────────────────
    # This happens when the document language wasn't detected correctly
    # at ingestion time (e.g. Sample.docx got language='unknown').
    if not results and query_filter is not None:
        log.warning(
            f"No chunks found for language='{lang}'. "
            f"Falling back to unfiltered search."
        )
        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=TOP_K,
            with_payload=True,
        ).points

    # ── Parse results ──────────────────────────────────────────────────────────
    # LangChain stores payload as:
    #   { "page_content": "...", "metadata": { "source": "...", "language": "..." } }
    chunks = []
    for hit in results:
        payload  = hit.payload or {}
        metadata = payload.get("metadata", {})

        chunks.append({
            "text":      payload.get("page_content", ""),
            "score":     round(hit.score, 4),
            "source":    metadata.get("source",    "unknown"),
            "language":  metadata.get("language",  "unknown"),
            "file_name": metadata.get("file_name", "unknown"),
        })

    return chunks


# ── Test block ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    # ── Test 1: English question with language filter ──────────────────────────
    print("=" * 58)
    print("TEST 1 — English question (language filter ON)")
    print("=" * 58)
    q1 = "What are the deliverables for this task?"
    lang1 = detect_query_language(q1)
    chunks1 = retrieve_chunks(q1, filter_language=True)

    print(f"Question        : {q1}")
    print(f"Detected lang   : {lang1}")
    print(f"Chunks returned : {len(chunks1)}\n")

    for i, c in enumerate(chunks1, 1):
        print(f"── Chunk {i} ──────────────────────────────────────────")
        print(f"  Score    : {c['score']}")
        print(f"  Language : {c['language']}")
        print(f"  File     : {c['file_name']}")
        print(f"  Source   : {c['source']}")
        print(f"  Text     : {c['text'][:200]}...")
        print()

    # ── Test 2: Same question WITHOUT filter (for comparison) ──────────────────
    print("=" * 58)
    print("TEST 2 — Same question (language filter OFF)")
    print("=" * 58)
    chunks2 = retrieve_chunks(q1, filter_language=False)
    print(f"Chunks returned : {len(chunks2)}\n")

    for i, c in enumerate(chunks2, 1):
        print(f"── Chunk {i} ──────────────────────────────────────────")
        print(f"  Score    : {c['score']}")
        print(f"  Language : {c['language']}")
        print(f"  File     : {c['file_name']}")
        print(f"  Text     : {c['text'][:200]}...")
        print()

    # ── Test 3: Verify scores are descending ───────────────────────────────────
    print("=" * 58)
    print("TEST 3 — Score order check")
    print("=" * 58)
    scores = [c['score'] for c in chunks2]
    is_descending = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
    print(f"Scores        : {scores}")
    print(f"Descending    : {'YES ✓' if is_descending else 'NO ✗ — something is wrong'}")