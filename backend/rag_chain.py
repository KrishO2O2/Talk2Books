# backend/rag_chain.py

from langchain_huggingface import HuggingFaceEmbeddings

# Must be identical to the model used in ingest.py
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"

# Load the model once at module level so it isn't reloaded on every call
embedder = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

def embed_query(question: str) -> list[float]:
    """
    Convert a user's question into a 768-dimensional vector.
    Uses the same model as ingest.py — critical for Qdrant search to work.
    """
    return embedder.embed_query(question)


# ── Quick test — run this file directly to verify ─────────────────────────────
if __name__ == "__main__":
    print("Script started...")   
    question = "What is this document about?"
    vector = embed_query(question)

    print(f"Question : {question}")
    print(f"Dimensions: {len(vector)}")          # Must print 768
    print(f"First 5 values: {vector[:5]}")       # Should be small floats
    print(f"Last  5 values: {vector[-5:]}")
    print("\nAll good!" if len(vector) == 768 else "\nERROR: wrong dimension!")