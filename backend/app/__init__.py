"""
Application package for APIProxy.

This package contains:
- settings: configuration and upstream header building
- logging_config: shared logging setup
- deps: FastAPI dependencies (Redis, HTTP client)
- context_store: conversation context persistence
- upstream: upstream API helpers (format detection, streaming)
- routes: FastAPI app factory and HTTP endpoints
"""
