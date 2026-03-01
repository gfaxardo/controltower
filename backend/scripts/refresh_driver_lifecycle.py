#!/usr/bin/env python3
"""
Punto de entrada para refresh Driver Lifecycle + validaciones post-refresh.
Equivalente a: python -m scripts.check_driver_lifecycle_and_validate
Con refresh (concurrently por defecto, fallback nonc) y validaciones:
  - Conteos por MV, unicidad base, freshness
  - Parks distintos, top 5 parks por activations, total activations (últimos 28 días)
No bloquea producción si falla drilldown/parks; solo loguea.
"""
import os
import sys

# Opcional: forzar modo y timeout por ENV
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.check_driver_lifecycle_and_validate import main
    main()
