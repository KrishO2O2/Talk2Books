# backend/rag_chain.py

from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient

# Must be identical to the model used in ingest.py
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
QDRANT_URL      = "http://localhost:6333"
COLLECTION_NAME = "ttb_documents"
TOP_K           = 3  # how many chunks to retrieve per query

# Load the model once at module level so it isn't reloaded on every call
embedder = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},  # Use CPU for embedding (no GPU needed for small scale)
    encode_kwargs={"normalize_embeddings": True},
)

# Connect to Qdrant once at module level (same pattern as embedder)
qdrant = QdrantClient(url=QDRANT_URL)

def embed_query(question: str) -> list[float]:
    """
    Convert a user's question into a 768-dimensional vector.
    Uses the same model as ingest.py — critical for Qdrant search to work.
    """
    return embedder.embed_query(question)

def retrieve_chunks(question: str) -> list[dict]:
    """
    Embed the question and search Qdrant for the top-k most similar chunks.
    Returns a list of dicts with 'text', 'score', 'source', and 'language'.
    """
    query_vector = embed_query(question)

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=TOP_K,
        with_payload=True,
    ).points

    chunks = []
    for hit in results:
        chunks.append({
            "text":     hit.payload.get("page_content", ""),
            "score":    round(hit.score, 4),
            "source":   hit.payload.get("source", "unknown"),
            "language": hit.payload.get("language", "unknown"),
        })

    return chunks

# ── Quick test — run this file directly to verify retrieval works.
if __name__ == "__main__":
    question = "What is this document about?"
    
    print(f"Question: {question}\n")
    print(f"Searching top {TOP_K} chunks...\n")
    
    chunks = retrieve_chunks(question)
    
    for i, chunk in enumerate(chunks, 1):
        print(f"--- Chunk {i} ------------------------------------------------")
        print(f"Score   : {chunk['score']}")
        print(f"Language: {chunk['language']}")
        print(f"Source  : {chunk['source']}")
        print(f"Text    : {chunk['text'][:200]}...")
        print()