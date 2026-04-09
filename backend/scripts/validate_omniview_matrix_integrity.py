"""
CLI del validador Omniview Matrix. La lógica vive en app.services.omniview_matrix_integrity_service.

  cd backend && python -m scripts.validate_omniview_matrix_integrity [--json]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.omniview_matrix_integrity_service import run_cli_main

if __name__ == "__main__":
    run_cli_main()
