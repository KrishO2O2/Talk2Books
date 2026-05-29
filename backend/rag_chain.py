"""
backend/rag_chain.py
Talk2Books — Phase 3
Day 1: embed_query()
Day 2: retrieve_chunks() with Qdrant search
Day 3: language detection + payload filtering + metadata fix
Day 4: build_prompt() — format chunks + question into LLM prompt
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

# ── System prompt template ─────────────────────────────────────────────────────
# This tells phi4 exactly what role it plays and how to behave.
# The {context} and {question} placeholders are filled in by build_prompt().
SYSTEM_PROMPT = """You are Talk2Books, a helpful document assistant.
Your job is to answer the user's question using ONLY the context passages provided below.

Rules you must follow:
- Answer based strictly on the provided context. Do not use outside knowledge.
- If the answer is not present in the context, say exactly:
  "I could not find an answer to your question in the provided documents."
- Be concise and direct. Do not repeat the question back.
- If the context is in a different language than the question, answer in the question's language.
- Cite the source filename at the end of your answer like this: [Source: filename]

Context passages:
{context}

Question: {question}

Answer:"""

# ── Module-level singletons ────────────────────────────────────────────────────
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

    # Build language filter using dot notation for nested metadata
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

    # Primary search
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=TOP_K,
        with_payload=True,
        query_filter=query_filter,
    ).points

    # Fallback: retry without language filter if nothing returned
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

    # Parse results — LangChain nests metadata under payload["metadata"]
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


# ── Day 4: Prompt Builder ──────────────────────────────────────────────────────

def build_prompt(question: str, chunks: list[dict]) -> str:
    """
    Format retrieved chunks and the user's question into a structured prompt
    ready to be sent to phi4.

    Each chunk is presented as a numbered passage with its source filename
    so phi4 can cite it in the answer.

    Args:
        question: The original user question string.
        chunks:   List of chunk dicts returned by retrieve_chunks().

    Returns:
        A fully formatted prompt string ready for the LLM.
    """
    if not chunks:
        # No context was retrieved — tell the model explicitly
        context_block = "No relevant passages were found in the documents."
    else:
        # Format each chunk as a numbered passage block
        # Showing the source file helps phi4 produce accurate citations
        passage_blocks = []
        for i, chunk in enumerate(chunks, 1):
            block = (
                f"[Passage {i} — Source: {chunk['file_name']}]\n"
                f"{chunk['text'].strip()}"
            )
            passage_blocks.append(block)

        # Join all passages with a clear separator between them
        context_block = "\n\n---\n\n".join(passage_blocks)

    # Fill the system prompt template with context and question
    prompt = SYSTEM_PROMPT.format(
        context=context_block,
        question=question,
    )

    return prompt


# ── Test block ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    question = "What are the deliverables for this task?"

    print("=" * 60)
    print("STEP 1 — Retrieving chunks from Qdrant")
    print("=" * 60)
    chunks = retrieve_chunks(question, filter_language=True)
    print(f"Retrieved {len(chunks)} chunk(s)\n")
    for i, c in enumerate(chunks, 1):
        print(f"  Chunk {i}: score={c['score']}  file={c['file_name']}")
    print()

    print("=" * 60)
    print("STEP 2 — Building the prompt")
    print("=" * 60)
    prompt = build_prompt(question, chunks)
    print(prompt)
    print()

    print("=" * 60)
    print("STEP 3 — Prompt stats")
    print("=" * 60)
    print(f"Total characters : {len(prompt)}")
    print(f"Total lines      : {prompt.count(chr(10))}")
    print(f"Passages included: {len(chunks)}")
    print(f"Question         : {question}")

    # Verify the question appears in the prompt
    q_present = question in prompt
    # Verify each chunk's text appears in the prompt
    all_chunks_present = all(c['text'].strip()[:50] in prompt for c in chunks)

    print()
    print(f"Question in prompt     : {'YES ✓' if q_present       else 'NO ✗'}")
    print(f"All chunks in prompt   : {'YES ✓' if all_chunks_present else 'NO ✗'}")
    print(f"Answer label present   : {'YES ✓' if 'Answer:' in prompt else 'NO ✗'}")