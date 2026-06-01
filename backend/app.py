"""
backend/app.py
Talk2Books — Phase 3 Day 6
Quart async API server — the HTTP bridge between React frontend and rag_chain.py

Endpoints:
    GET  /api/health  — health check, confirms server + Qdrant + Ollama are up
    POST /api/query   — receives a question, returns an answer from the RAG pipeline
"""

import logging
from quart import Quart, request, jsonify
from quart_cors import cors
from rag_chain import ask
from qdrant_client import QdrantClient
import httpx

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("ttb.app")

# Silence noisy HTTP logs from qdrant and httpx clients
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ── App setup ──────────────────────────────────────────────────────────────────
app = Quart(__name__)

# cors() allows the React dev server (localhost:3000) to call this API
# (localhost:5000) without the browser blocking the request.
# allow_origin="*" permits all origins — fine for local development.
app = cors(app, allow_origin="*")

# Qdrant client for health check only
qdrant_client = QdrantClient(url="http://localhost:6333")


# ── GET /api/health ────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
async def health():
    """
    Health check endpoint.
    Checks that both Qdrant and Ollama are reachable before reporting healthy.
    The frontend can call this on load to show a 'connected' indicator.
    """
    status = {
        "server":  "ok",
        "qdrant":  "unknown",
        "ollama":  "unknown",
    }

    # Check Qdrant
    try:
        collections = qdrant_client.get_collections()
        names = [c.name for c in collections.collections]
        status["qdrant"] = "ok" if "ttb_documents" in names else "missing_collection"
    except Exception as e:
        log.warning(f"Qdrant health check failed: {e}")
        status["qdrant"] = "unreachable"

    # Check Ollama
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:11434", timeout=3.0)
            status["ollama"] = "ok" if resp.status_code == 200 else "error"
    except Exception as e:
        log.warning(f"Ollama health check failed: {e}")
        status["ollama"] = "unreachable"

    # Overall health
    all_ok = all(v == "ok" for v in status.values())
    status["healthy"] = all_ok

    http_status = 200 if all_ok else 503
    log.info(f"Health check: {status}")
    return jsonify(status), http_status


# ── POST /api/query ────────────────────────────────────────────────────────────

@app.route("/api/query", methods=["POST"])
async def query():
    """
    Main RAG query endpoint.

    Expects JSON body:
        { "question": "What are the deliverables?" }

    Optional:
        { "question": "...", "filter_language": false }

    Returns JSON:
        {
            "answer":   "The deliverables include...",
            "sources":  ["Sample.docx"],
            "language": "en",
            "chunks":   [ { "text": "...", "score": 0.32, ... } ]
        }

    Error response (400):
        { "error": "Question is required." }
    """
    # Parse incoming JSON body
    data = await request.get_json()

    # Validate — question must be present and non-empty
    if not data or not data.get("question", "").strip():
        log.warning("Received request with missing or empty question.")
        return jsonify({"error": "Question is required."}), 400

    question        = data["question"].strip()
    filter_language = data.get("filter_language", True)

    log.info(f"Received question: '{question}' | filter_language={filter_language}")

    # Call the RAG pipeline
    # ask() handles all errors internally and returns a safe response
    result = ask(question, filter_language=filter_language)

    log.info(f"Returning answer ({len(result['answer'])} chars) from {result['sources']}")

    return jsonify({
        "answer":   result["answer"],
        "sources":  result["sources"],
        "language": result["language"],
        "chunks":   result["chunks"],
    }), 200


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting Talk2Books API server...")
    log.info("Endpoints:")
    log.info("  GET  http://localhost:5000/api/health")
    log.info("  POST http://localhost:5000/api/query")

    # debug=False in production, but True here gives auto-reload on file save
    app.run(host="0.0.0.0", port=5000, debug=True)