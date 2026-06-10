"""
backend/rag_chain.py
Talk2Books — Phase 3
Day 1: embed_query()
Day 2: retrieve_chunks() with Qdrant search
Day 3: language detection + payload filtering + metadata fix
Day 4: build_prompt() — format chunks + question into LLM prompt
Day 5: generate_answer() — send prompt to phi4-mini via ChatOllama
Day 6: silence noisy HuggingFace HTTP logs
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

# Silence the noisy HuggingFace HTTP request logs — they flood the terminal
# and make it hard to see actual application logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

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
embedder = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

qdrant = QdrantClient(url=QDRANT_URL)

llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.1,
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
    Returns 'unknown' if detection fails.
    """
    try:
        return detect(question)
    except LangDetectException:
        log.warning("Language detection failed — defaulting to 'unknown'.")
        return "unknown"


# ── Day 2 + 3: Retrieval with Language Filter ──────────────────────────────────

def retrieve_chunks(question: str, filter_language: bool = True, language: str | None = None) -> list[dict]:
    query_vector = embed_query(question)
    lang = language if language else detect_query_language(question)
    log.info(f"Query language: '{lang}' ({'manual' if language else 'auto-detected'})")

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
        log.warning(f"No chunks for language='{lang}'. Falling back to unfiltered search.")
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
    prompt ready to be sent to phi4-mini.
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
    Send the formatted prompt to phi4-mini via Ollama and return the answer.
    """
    log.info("Sending prompt to phi4-mini via Ollama...")
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        answer   = response.content.strip()
        log.info("Answer received from phi4-mini.")
        return answer
    except Exception as e:
        log.error(f"Ollama call failed: {e}")
        return (
            "Sorry, I could not reach the language model. "
            "Please make sure Ollama is running with: ollama run phi4-mini"
        )


# ── Day 5: Full pipeline ───────────────────────────────────────────────────────

def ask(question: str, filter_language: bool = True, language: str | None = None) -> dict:

    chunks  = retrieve_chunks(question, filter_language=filter_language, language=language)
    """
    The complete RAG pipeline in one call.
    This is the single function that app.py calls.

    Returns dict with: answer, sources, language, chunks.
    """
    log.info(f"Pipeline started for: '{question}'")

    prompt  = build_prompt(question, chunks)
    answer  = generate_answer(prompt)
    sources = list({c["file_name"] for c in chunks if c["file_name"] != "unknown"})
    lang    = detect_query_language(question)

    return {
        "answer":   answer,
        "sources":  sources,
        "language": lang,
        "chunks":   chunks,
    }


# ── Quick smoke test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = ask("What are the deliverables for this task?")
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Language: {result['language']}")