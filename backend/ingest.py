"""
backend/ingest.py
Talk2Books — Phase 2: Data Ingestion & Chunking
Implements Module 1 (Data Ingestion & Preprocessing) and
Module 2 (Document Splitting) from the TTB specification.
"""

import logging
import unicodedata
from pathlib import Path
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    CSVLoader,
)
from langchain_core.documents import Document
from langdetect import detect, LangDetectException
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_huggingface import HuggingFaceEmbeddings

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
log = logging.getLogger("ttb.ingest")

# ── Config ─────────────────────────────────────────────────────────────────────
# Spec Module 3: "all-mpnet-base-v2" → 768 dimensions
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIM   = 768

# Spec Module 2: configurable chunk size & overlap
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50

# Qdrant
QDRANT_URL       = "http://localhost:6333"
COLLECTION_NAME  = "ttb_documents"

# Spec Module 1: supported source formats
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".csv"}


# ── Text Normalisation (Module 1) ──────────────────────────────────────────────

def normalize_text(text: str, lowercase: bool = False) -> str:
    """
    Normalize raw text per spec Module 1:
      - Enforce UTF-8 compatible unicode (NFC normalization)
      - Collapse whitespace
      - Optional lowercasing (controlled by config param)
    """
    # Unicode NFC normalization keeps multi-script characters intact
    text = unicodedata.normalize("NFC", text)

    # Collapse runs of whitespace / non-printing chars to a single space
    text = " ".join(text.split())

    if lowercase:
        text = text.lower()

    return text


# ── Language Detection (Module 1) ─────────────────────────────────────────────

def detect_language(text: str) -> str:
    """
    Detect the language of a text snippet.
    Returns an ISO 639-1 code (e.g. 'en', 'hi', 'pa') or 'unknown'.
    Spec: "Utilize a library like langdetect. Store language information
    with the document metadata."
    """
    try:
        # Use a meaningful sample — langdetect works better with ≥50 chars
        sample = text[:500]
        return detect(sample)
    except LangDetectException:
        log.warning("Language detection failed; defaulting to 'unknown'.")
        return "unknown"


# ── Document Loading (Module 1) ────────────────────────────────────────────────

def load_document(file_path: Path) -> list[Document]:
    """
    Load a single file into a list of LangChain Documents.
    Supports: .txt, .pdf, .docx, .csv
    Raises ValueError for unsupported extensions.
    """
    ext = file_path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {SUPPORTED_EXTENSIONS}"
        )

    log.info(f"Loading '{file_path.name}' (type: {ext})")

    try:
        if ext == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
        elif ext == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif ext == ".docx":
            loader = Docx2txtLoader(str(file_path))
        elif ext == ".csv":
            loader = CSVLoader(str(file_path), encoding="utf-8")

        docs = loader.load()
    except Exception as exc:
        log.error(f"Failed to load '{file_path.name}': {exc}")
        raise

    return docs


def load_all_documents(data_dir: str = "data") -> list[Document]:
    """
    Walk the data/ directory and load every supported file.
    Attaches normalized text and detected language to metadata.
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: '{data_dir}'")

    all_docs: list[Document] = []

    for file_path in sorted(data_path.rglob("*")):
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            docs = load_document(file_path)

            for doc in docs:
                # Module 1 — normalize content
                doc.page_content = normalize_text(doc.page_content)

                # Module 1 — detect & store language in metadata
                lang = detect_language(doc.page_content)
                doc.metadata["language"]  = lang
                doc.metadata["source"]    = str(file_path)
                doc.metadata["file_name"] = file_path.name

            all_docs.extend(docs)
            log.info(f"  → Loaded {len(docs)} page(s) from '{file_path.name}'")

        except Exception as exc:
            # Module 1 — robust error handling: log and continue
            log.error(f"  ✗ Skipping '{file_path.name}': {exc}")
            continue

    log.info(f"Total documents loaded: {len(all_docs)}")
    return all_docs


# ── Document Splitting (Module 2) ─────────────────────────────────────────────

def split_documents(
    docs: list[Document],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    """
    Split documents into chunks using RecursiveCharacterTextSplitter.
    Spec Module 2:
      - Configurable chunk_size and chunk_overlap
      - Recursive splitter respects sentence/paragraph boundaries
        (separators: paragraph → newline → sentence → word → char)
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # These separators try paragraph → sentence → word boundaries
        # before character-level splitting, preserving semantic context.
        separators=["\n\n", "\n", "। ", "। \n", ". ", " ", ""],
        length_function=len,
    )

    chunks = splitter.split_documents(docs)
    log.info(
        f"Split {len(docs)} document(s) into {len(chunks)} chunk(s) "
        f"(size={chunk_size}, overlap={chunk_overlap})"
    )
    return chunks


# ── Qdrant Ingestion (Module 4) ────────────────────────────────────────────────

def get_or_create_collection(client: QdrantClient) -> None:
    """
    Create the Qdrant collection if it doesn't already exist.
    Uses cosine distance with all-mpnet-base-v2 dimension (768).
    """
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,   # must match EMBEDDING_MODEL output
                distance=Distance.COSINE,
            ),
        )
        log.info(f"Created Qdrant collection '{COLLECTION_NAME}'")
    else:
        log.info(f"Collection '{COLLECTION_NAME}' already exists — skipping creation.")


def ingest(
    data_dir: str = "data",
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    qdrant_url: str = QDRANT_URL,
    embedding_model: Optional[str] = None,
) -> int:
    """
    Full ingestion pipeline:
      1. Load all documents from data_dir
      2. Normalise & detect languages
      3. Split into chunks
      4. Embed with sentence-transformers
      5. Upsert into Qdrant

    Returns the total number of chunks ingested.
    """
    model_name = embedding_model or EMBEDDING_MODEL

    # Step 1 + 2 — Load & preprocess
    docs = load_all_documents(data_dir)
    if not docs:
        log.warning("No documents found. Place files in the 'data/' directory.")
        return 0

    # Step 3 — Chunk
    chunks = split_documents(docs, chunk_size, chunk_overlap)

    # Step 4 — Embeddings (cached by sentence-transformers locally)
    log.info(f"Loading embedding model '{model_name}'…")
    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "mps"},   # changed to "mps" for Apple Silicon GPU
        encode_kwargs={"normalize_embeddings": True},
    )

    # Step 5 — Qdrant upsert
    log.info(f"Connecting to Qdrant at {qdrant_url}…")
    client = QdrantClient(url=qdrant_url)
    get_or_create_collection(client)

    # Batch-embed and upsert in one call via langchain_qdrant
    from langchain_qdrant import QdrantVectorStore

    QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        url=qdrant_url,
        collection_name=COLLECTION_NAME,
        force_recreate=False,   # set True to wipe & rebuild the collection
    )

    log.info(f"✓ Ingestion complete — {len(chunks)} chunk(s) stored in Qdrant.")
    return len(chunks)


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TTB data ingestion pipeline")
    parser.add_argument("--data-dir",      default="data",            help="Path to your documents folder")
    parser.add_argument("--chunk-size",    type=int, default=CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP)
    parser.add_argument("--qdrant-url",    default=QDRANT_URL)
    parser.add_argument("--embedding-model", default=EMBEDDING_MODEL)
    args = parser.parse_args()

    total = ingest(
        data_dir=args.data_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        qdrant_url=args.qdrant_url,
        embedding_model=args.embedding_model,
    )
    print(f"\nDone. {total} chunk(s) ingested.")
