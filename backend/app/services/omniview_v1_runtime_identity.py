"""
OMNI-V1 HARDENING — Runtime Identity.

Provides runtime metadata to identify exactly which backend instance is serving,
when it started, what code version it runs, and its environment.

Used by: health endpoint extension and V1 Trust Sensor audit.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
from datetime import datetime, timezone
from typing import Any

# ────────────────────────────────────────────
# cached identity — computed once at import time
# ────────────────────────────────────────────


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def _git_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def _app_start_time() -> str:
    return _APP_START_TIME


def _backend_instance() -> str:
    pid = os.getpid()
    host = platform.node()
    return f"{host}:{pid}"


def _loaded_module_paths() -> list[str]:
    paths: list[str] = []
    # Key V1 modules to verify
    v1_modules = [
        "app.services.business_slice_omniview_service",
        "app.services.business_slice_service",
        "app.services.business_slice_real_freshness_service",
        "app.services.omniview_v1_trust_sensor",
        "app.services.omniview_matrix_integrity_service",
    ]
    for mod_name in v1_modules:
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "__file__") and mod.__file__:
            paths.append({"module": mod_name, "path": mod.__file__})
        else:
            paths.append({"module": mod_name, "path": None})
    return paths


def _pycache_risk_checked() -> dict[str, Any]:
    backend_dir = os.path.join(os.path.dirname(__file__), "..")
    total = 0
    stale = 0
    for root, dirs, files in os.walk(backend_dir):
        if "__pycache__" in root:
            for f in files:
                if not f.endswith(".pyc"):
                    continue
                total += 1
                pyc_path = os.path.join(root, f)
                pyc_mtime = os.path.getmtime(pyc_path)
                # find matching .py
                py_name = f.split(".cpython-")[0] + ".py"
                src_path = os.path.join(os.path.dirname(root), py_name)
                if os.path.exists(src_path):
                    if pyc_mtime < os.path.getmtime(src_path):
                        stale += 1
    return {
        "total_pyc_files": total,
        "stale_pyc_files": stale,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


_APP_START_TIME = datetime.now(timezone.utc).isoformat()
_RUNTIME_IDENTITY_CACHE_LOCK = threading.Lock()
_RUNTIME_IDENTITY_CACHE: dict[str, Any] | None = None


def get_v1_runtime_identity() -> dict[str, Any]:
    global _RUNTIME_IDENTITY_CACHE

    with _RUNTIME_IDENTITY_CACHE_LOCK:
        if _RUNTIME_IDENTITY_CACHE:
            return _RUNTIME_IDENTITY_CACHE

        _RUNTIME_IDENTITY_CACHE = {
            "git_hash": _git_commit(),
            "git_branch": _git_branch(),
            "build_time": _APP_START_TIME,
            "backend_instance": _backend_instance(),
            "python_version": sys.version,
            "app_start_time": _APP_START_TIME,
            "loaded_module_paths": _loaded_module_paths(),
            "pycache_risk_checked": _pycache_risk_checked(),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return _RUNTIME_IDENTITY_CACHE
