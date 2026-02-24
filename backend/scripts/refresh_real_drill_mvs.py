#!/usr/bin/env python3
"""
Las vistas de drill (ops.v_real_drill_*) son vistas que leen de
ops.mv_real_lob_month_v2 y ops.mv_real_lob_week_v2. Para que el drill-down
tenga datos actualizados, hay que refrescar esas MVs.

Este script ejecuta el refresh de las MVs v2 (mismo que refresh_real_lob_mvs_v2).
Uso: desde backend/ ejecutar python -m scripts.refresh_real_drill_mvs
Recomendado: refresh diario tras ingesta.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

# Delegar en el script existente de v2
from scripts.refresh_real_lob_mvs_v2 import main

if __name__ == "__main__":
    main()
