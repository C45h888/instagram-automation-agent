"""
API Key Middleware
==================
Enforces X-API-Key authentication on all routes except explicitly public ones.
Replaces per-route @require_api_key decorators with a single before_request hook.
"""

import os
from flask import request, jsonify

# Paths that skip authentication (opt-in allowlist)
PUBLIC_PATHS = {"/health", "/metrics"}


def api_key_middleware(app):
    """Register a before_request hook that checks X-API-Key on protected routes."""
    api_key = os.getenv("AGENT_API_KEY", "")

    @app.before_request
    def check_api_key():
        # Skip auth for public endpoints
        if request.path in PUBLIC_PATHS:
            return None

        # If no key configured, skip auth (dev mode)
        if not api_key:
            return None

        provided = request.headers.get("X-API-Key", "")
        if provided != api_key:
            return jsonify({
                "error": "unauthorized",
                "message": "Invalid or missing X-API-Key header"
            }), 401

        return None
