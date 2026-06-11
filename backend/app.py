"""
backend/app.py
Talk2Books — Phase 3 Day 6 (updated Day 7)
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

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ── Config ─────────────────────────────────────────────────────────────────────
MAX_QUESTION_LENGTH = 1000   # characters — prevents absurdly long inputs
MIN_QUESTION_LENGTH = 3      # characters — prevents single-character nonsense

# ── App setup ──────────────────────────────────────────────────────────────────
app = Quart(__name__)
app = cors(app, allow_origin="*")

qdrant_client = QdrantClient(url="http://localhost:6333")


# ── GET /api/health ────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
async def health():
    """
    Health check endpoint.
    Checks that both Qdrant and Ollama are reachable.
    Returns 200 if healthy, 503 if any service is down.
    """
    status = {
        "server": "ok",
        "qdrant": "unknown",
        "ollama": "unknown",
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

    all_ok = all(v == "ok" for v in status.values())
    status["healthy"] = all_ok

    log.info(f"Health check: {status}")
    return jsonify(status), 200 if all_ok else 503

# ── GET /api/documents ─────────────────────────────────────────────────────────

@app.route("/api/documents", methods=["GET"])
async def documents():
    """
    Returns a deduplicated list of ingested documents by scrolling Qdrant.
    Each unique file_name in the collection becomes one document entry.
    """
    try:
        seen   = {}
        offset = None

        while True:
            points, next_offset = qdrant_client.scroll(
                collection_name="ttb_documents",
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for point in points:
                payload   = point.payload or {}
                metadata  = payload.get("metadata", {})
                file_name = metadata.get("file_name", "unknown")

                if file_name != "unknown" and file_name not in seen:
                    seen[file_name] = {
                        "id":       file_name,
                        "name":     file_name,
                        "language": metadata.get("language", "unknown"),
                    }

            if next_offset is None:
                break
            offset = next_offset

        doc_list = sorted(seen.values(), key=lambda d: d["name"])
        log.info(f"/api/documents: returning {len(doc_list)} document(s)")
        return jsonify({"documents": doc_list}), 200

    except Exception as e:
        log.error(f"Failed to fetch documents: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve documents from Qdrant."}), 500

# ── POST /api/query ────────────────────────────────────────────────────────────

@app.route("/api/query", methods=["POST"])
async def query():
    """
    Main RAG query endpoint.

    Expects JSON body:
        { "question": "What are the deliverables?" }

    Optional:
        { "question": "...", "filter_language": false }

    Returns 200 with answer JSON, or 400/500 with error message.
    """
    # ── Parse body ─────────────────────────────────────────────────────────────
    try:
        data = await request.get_json(force=True, silent=True)
    except Exception:
        data = None

    # ── Validate: body must be a JSON object ───────────────────────────────────
    if not isinstance(data, dict):
        log.warning("Request body is not valid JSON.")
        return jsonify({
            "error": "Request body must be valid JSON with a 'question' field."
        }), 400

    # ── Validate: question must be present ─────────────────────────────────────
    question = data.get("question", "")

    if not isinstance(question, str):
        log.warning(f"Question field is not a string: {type(question)}")
        return jsonify({
            "error": "The 'question' field must be a string."
        }), 400

    question = question.strip()

    if len(question) < MIN_QUESTION_LENGTH:
        log.warning(f"Question too short: '{question}'")
        return jsonify({
            "error": f"Question must be at least {MIN_QUESTION_LENGTH} characters."
        }), 400

    # ── Validate: question must not be too long ────────────────────────────────
    if len(question) > MAX_QUESTION_LENGTH:
        log.warning(f"Question too long: {len(question)} chars")
        return jsonify({
            "error": f"Question must be under {MAX_QUESTION_LENGTH} characters."
        }), 400

    filter_language = data.get("filter_language", True)
    if not isinstance(filter_language, bool):
        filter_language = True   # safe default if someone sends a weird value

    language = data.get("language", None)
    doc_id = data.get("doc_id", None)

    log.info(f"Question: '{question}' | filter_language={filter_language} | language={language}")

    # ── Run the RAG pipeline ───────────────────────────────────────────────────
    try:
        result = ask(question, filter_language=filter_language, language=language, doc_id=doc_id)
    except Exception as e:
        # Catch any unexpected pipeline errors so the server never crashes
        log.error(f"Pipeline error: {e}", exc_info=True)
        return jsonify({
            "error": "An internal error occurred. Please try again."
        }), 500

    log.info(f"Answer ready ({len(result['answer'])} chars) | sources: {result['sources']}")

    return jsonify({
        "answer":   result["answer"],
        "sources":  result["sources"],
        "language": result["language"],
        "chunks":   result["chunks"],
    }), 200


# ── 404 handler ────────────────────────────────────────────────────────────────

@app.errorhandler(404)
async def not_found(e):
    return jsonify({"error": "Endpoint not found."}), 404


# ── 405 handler ────────────────────────────────────────────────────────────────

@app.errorhandler(405)
async def method_not_allowed(e):
    return jsonify({"error": "Method not allowed."}), 405


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting Talk2Books API server...")
    log.info("Endpoints:")
    log.info("  GET  http://localhost:5000/api/health")
    log.info("  POST http://localhost:5000/api/query")
    app.run(host="0.0.0.0", port=5000, debug=True)