"""
LangChain Oversight Brain Agent
================================
Central approval authority for Instagram automation N8N workflows.
Receives proposed actions (comment replies, DM replies, posts),
analyzes them using NVIDIA Nemotron 4 8B via Ollama,
and returns approve/reject/modify decisions.

Endpoints:
  GET  /health                 - Health check (Ollama + Supabase status)
  POST /approve/comment-reply  - Approve/reject comment reply
  POST /approve/dm-reply       - Approve/reject DM reply (with escalation)
  POST /approve/post           - Approve/reject post caption
"""

import os
from flask import Flask, jsonify
from config import logger, OLLAMA_HOST, OLLAMA_MODEL

# Import route blueprints
from routes import health_bp, approve_comment_bp, approve_dm_bp, approve_post_bp


def create_app():
    """Flask application factory."""
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(approve_comment_bp)
    app.register_blueprint(approve_dm_bp)
    app.register_blueprint(approve_post_bp)

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
    logger.info(f"  Endpoints: /health, /approve/comment-reply, /approve/dm-reply, /approve/post")
    logger.info("=" * 60)

    return app


# Create the app instance (used by gunicorn: gunicorn agent:app)
app = create_app()

# Dev server fallback
if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 3002))
    app.run(host="0.0.0.0", port=port, debug=True)
