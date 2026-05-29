"""
backend/rag_chain.py
Talk2Books — Phase 3
Day 1: embed_query()
Day 2: retrieve_chunks() with Qdrant search
Day 3: language detection + payload filtering + metadata fix
Day 4: build_prompt() — format chunks + question into LLM prompt
Day 5: generate_answer() — send prompt to phi4 via ChatOllama
"""

import logging
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
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
OLLAMA_MODEL    = "phi4-mini"
OLLAMA_BASE_URL = "http://localhost:11434"
TOP_K           = 3

# ── System prompt template ─────────────────────────────────────────────────────
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
# Loaded once when the module is imported — not on every function call
embedder = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

qdrant = QdrantClient(url=QDRANT_URL)

llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.1,   # low temperature = focused, factual answers
                       # 0.0 = fully deterministic, 1.0 = creative/random
)


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

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=TOP_K,
        with_payload=True,
        query_filter=query_filter,
    ).points

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
    Format retrieved chunks and the user's question into a structured
    prompt ready to be sent to phi4.
    """
    if not chunks:
        context_block = "No relevant passages were found in the documents."
    else:
        passage_blocks = []
        for i, chunk in enumerate(chunks, 1):
            block = (
                f"[Passage {i} — Source: {chunk['file_name']}]\n"
                f"{chunk['text'].strip()}"
            )
            passage_blocks.append(block)
        context_block = "\n\n---\n\n".join(passage_blocks)

    return SYSTEM_PROMPT.format(
        context=context_block,
        question=question,
    )


# ── Day 5: LLM Answer Generation ──────────────────────────────────────────────

def generate_answer(prompt: str) -> str:
    """
    Send the formatted prompt to phi4 via Ollama and return the answer.

    Uses HumanMessage because we pass the full system prompt + context
    as one message — phi4 handles it as a single instruction block.

    Args:
        prompt: The fully formatted prompt string from build_prompt().

    Returns:
        The answer string generated by phi4.
    """
    log.info("Sending prompt to phi4 via Ollama...")

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        answer   = response.content.strip()
        log.info("Answer received from phi4.")
        return answer

    except Exception as e:
        log.error(f"Ollama call failed: {e}")
        return (
            "Sorry, I could not reach the language model. "
            "Please make sure Ollama is running with: ollama run phi4"
        )


# ── Day 5: Full pipeline convenience function ──────────────────────────────────

def ask(question: str, filter_language: bool = True) -> dict:
    """
    The complete RAG pipeline in one call.
    This is the single function that app.py will call.

    Flow:
        question → embed → Qdrant search → build prompt → phi4 → answer

    Args:
        question:        The user's question string.
        filter_language: Whether to apply language-aware Qdrant filtering.

    Returns:
        Dict with keys:
            answer   — the generated answer string
            sources  — list of source filenames used
            language — detected query language
            chunks   — the raw retrieved chunks (for debugging)
    """
    log.info(f"Pipeline started for question: '{question}'")

    # Step 1: Retrieve
    chunks = retrieve_chunks(question, filter_language=filter_language)
    log.info(f"Retrieved {len(chunks)} chunk(s) from Qdrant.")

    # Step 2: Build prompt
    prompt = build_prompt(question, chunks)

    # Step 3: Generate
    answer = generate_answer(prompt)

    # Collect unique source filenames for the response
    sources = list({c["file_name"] for c in chunks if c["file_name"] != "unknown"})
    lang    = detect_query_language(question)

    return {
        "answer":   answer,
        "sources":  sources,
        "language": lang,
        "chunks":   chunks,
    }


# ── Test block ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    questions = [
        "What are the deliverables for this task?",
        "What validation rules apply to the span field?",
    ]

    for question in questions:
        print("\n" + "=" * 60)
        print(f"QUESTION: {question}")
        print("=" * 60)

        result = ask(question)

        print(f"\nDETECTED LANGUAGE : {result['language']}")
        print(f"SOURCES USED      : {result['sources']}")
        print(f"CHUNKS RETRIEVED  : {len(result['chunks'])}")
        print(f"SCORES            : {[c['score'] for c in result['chunks']]}")
        print(f"\nANSWER:\n{result['answer']}")
        print()