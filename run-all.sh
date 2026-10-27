#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

UVICORN="$ROOT/backend/.venv/bin/uvicorn"
if [[ ! -x "$UVICORN" ]]; then
  echo "No está el venv del backend en backend/.venv." >&2
  echo "Crea el entorno e instala dependencias:" >&2
  echo "  python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

PIDS=()

cleanup() {
  trap - EXIT INT TERM
  echo ""
  echo "Deteniendo front y back…"
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Backend  → http://127.0.0.1:8000"
(
  cd "$ROOT/backend"
  exec "$UVICORN" app.main:app --reload --host 127.0.0.1 --port 8000
) &
PIDS+=("$!")

if ! command -v npm >/dev/null 2>&1; then
  NVM_NPM="$(ls -d "$HOME/.nvm/versions/node"/*/bin/npm 2>/dev/null | tail -1 || true)"
  if [[ -n "${NVM_NPM:-}" ]]; then
    export PATH="$(dirname "$NVM_NPM"):$PATH"
  fi
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "No se encontró npm. Instala Node 20+ o carga nvm en esta terminal." >&2
  exit 1
fi

echo "Frontend → http://localhost:3000"
(
  cd "$ROOT"
  exec npm run dev
) &
PIDS+=("$!")

echo "Ctrl+C para detener ambos."
wait
