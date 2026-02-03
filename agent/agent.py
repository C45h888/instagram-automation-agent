"""
LangChain Oversight Brain Agent
================================
Central approval authority for Instagram automation N8N workflows.
Receives proposed actions (comment replies, DM replies, posts),
analyzes them using NVIDIA Nemotron 4 8B via Ollama,
and returns approve/reject/modify decisions.

Endpoints:
  GET  /health                 - Health check (Ollama + Supabase status)
  GET  /metrics                - Prometheus metrics
  POST /approve/comment-reply  - Approve/reject comment reply
  POST /approve/dm-reply       - Approve/reject DM reply (with escalation)
  POST /approve/post           - Approve/reject post caption
"""

import os
from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import logger, OLLAMA_HOST, OLLAMA_MODEL
from middleware import api_key_middleware

# Import route blueprints
from routes import health_bp, approve_comment_bp, approve_dm_bp, approve_post_bp, metrics_bp


def create_app():
    """Flask application factory."""
    app = Flask(__name__)

    # --- Middleware: API key auth ---
    api_key_middleware(app)

    # --- Rate limiting (Redis-backed for distributed state) ---
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = os.getenv("REDIS_PORT", "6379")

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["60 per minute"],
        storage_uri=f"redis://{redis_host}:{redis_port}",
        strategy="fixed-window",
    )

    # Stricter limits on approval endpoints
    limiter.limit("30 per minute")(approve_comment_bp)
    limiter.limit("30 per minute")(approve_dm_bp)
    limiter.limit("30 per minute")(approve_post_bp)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(approve_comment_bp)
    app.register_blueprint(approve_dm_bp)
    app.register_blueprint(approve_post_bp)
    app.register_blueprint(metrics_bp)

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            "error": "not_found",
            "message": "Endpoint not found. Available: /health, /approve/comment-reply, /approve/dm-reply, /approve/post"
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({
            "error": "method_not_allowed",
            "message": "Use POST for /approve/* endpoints, GET for /health"
        }), 405

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({
            "error": "rate_limited",
            "message": "Too many requests. Please slow down."
        }), 429

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Unhandled error: {e}")
        return jsonify({
            "error": "internal_error",
            "message": "An unexpected error occurred. Check agent logs."
        }), 500

    # Startup info
    logger.info("=" * 60)
    logger.info("Oversight Brain Agent starting up")
    logger.info(f"  Ollama Host: {OLLAMA_HOST}")
    logger.info(f"  Model: {OLLAMA_MODEL}")
    logger.info(f"  Rate Limit: 60/min global, 30/min on /approve/*")
    logger.info(f"  Endpoints: /health, /metrics, /approve/comment-reply, /approve/dm-reply, /approve/post")
    logger.info("=" * 60)

    return app


# Create the app instance (used by gunicorn: gunicorn agent:app)
app = create_app()

# Dev server fallback
if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 3002))
    app.run(host="0.0.0.0", port=port, debug=True)
