#!/usr/bin/env bash
# Control Tower — arranca API (FastAPI) y UI (Vite) en paralelo.
# Uso: ./dev.sh     Parar: Ctrl+C
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

if [[ ! -d "$BACKEND/venv" ]]; then
  echo "No existe backend/venv. Crea el entorno e instala dependencias:"
  echo "  cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -d "$FRONTEND/node_modules" ]]; then
  echo "Instalando dependencias del frontend..."
  (cd "$FRONTEND" && npm install)
fi

echo ""
echo "  → API:    http://127.0.0.1:8000  (docs: /docs)"
echo "  → Web:    http://localhost:5173"
echo ""

cleanup() {
  kill "${BACK_PID:-}" "${FRONT_PID:-}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(
  cd "$BACKEND"
  # shellcheck source=/dev/null
  source venv/bin/activate
  exec uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACK_PID=$!

(
  cd "$FRONTEND"
  exec npm run dev
) &
FRONT_PID=$!

wait "${BACK_PID}" "${FRONT_PID}" || true
