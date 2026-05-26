"""Thin re-export of the auth-service FastAPI ``app`` for test consumption.

The real ``services/auth-service/main.py`` uses a ``lifespan`` that connects
to Postgres and Redis on startup.  Tests override those dependencies via
``app.dependency_overrides``, but the lifespan still fires inside
``ASGITransport``.  To avoid that, we import the module and swap the lifespan
for a no-op **before** handing the app to test fixtures.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

# Ensure auth-service directory is on the path so ``main`` resolves.
_service_dir = os.path.join(os.path.dirname(__file__), "auth-service")
if _service_dir not in sys.path:
    sys.path.insert(0, _service_dir)

# Also need repo root for shared imports used by main.py
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Import the real app object
from main import app as _real_app  # noqa: E402


@asynccontextmanager
async def _noop_lifespan(app):
    yield


# Replace the heavy lifespan with a no-op for test isolation
_real_app.router.lifespan_context = _noop_lifespan

app = _real_app
