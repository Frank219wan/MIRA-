#!/bin/sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
frontend_dir="$root_dir/frontend-preview"
python="$frontend_dir/.runtime/latest-backend-venv/bin/python"

if [ ! -x "$python" ]; then
  echo "Missing Python environment: $python" >&2
  echo "Run the setup commands in LOCAL_SETUP.md first." >&2
  exit 1
fi
if [ ! -d "$frontend_dir/node_modules" ]; then
  echo "Missing frontend dependencies. Run npm ci in $frontend_dir first." >&2
  exit 1
fi

mkdir -p "$frontend_dir/.runtime"
export PYTHONPATH="$root_dir:$frontend_dir"
export PYTHONDONTWRITEBYTECODE=1
export MIRA_FACE_MODEL_PATH="${MIRA_FACE_MODEL_PATH:-$frontend_dir/public/models/face/face_landmarker.task}"
export MPLCONFIGDIR="$frontend_dir/.runtime/matplotlib"
export MIRA_DATABASE_URL="${MIRA_DATABASE_URL:-sqlite:///$frontend_dir/.runtime/mira_week1.db}"

cleanup() {
  kill "${backend_pid:-}" "${frontend_pid:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$frontend_dir"
"$python" -m uvicorn integration.app:app --host 127.0.0.1 --port 8000 \
  >.runtime/backend.log 2>&1 &
backend_pid=$!

attempt=0
until curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; do
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    cat .runtime/backend.log >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 150 ]; then
    echo "Backend did not become healthy within 30 seconds." >&2
    exit 1
  fi
  sleep 0.2
done

npm run dev -- --port 5173 >.runtime/frontend.log 2>&1 &
frontend_pid=$!

attempt=0
until curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; do
  if ! kill -0 "$frontend_pid" 2>/dev/null; then
    cat .runtime/frontend.log >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 150 ]; then
    echo "Frontend did not become reachable within 30 seconds." >&2
    exit 1
  fi
  sleep 0.2
done

echo "MIRA frontend: http://127.0.0.1:5173"
echo "MIRA backend:  http://127.0.0.1:8000"
echo "Logs: $frontend_dir/.runtime/{frontend,backend}.log"
echo "Press Ctrl-C to stop both services."

if [ "${MIRA_NO_BROWSER:-0}" != "1" ] && [ "$(uname -s)" = "Darwin" ]; then
  open http://127.0.0.1:5173 >/dev/null 2>&1 || true
fi

wait "$backend_pid" "$frontend_pid"
