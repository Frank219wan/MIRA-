#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
backend_dir="${MIRA_BACKEND_DIR:-../MIRA--main-2}"
export PYTHONPATH="$backend_dir:$PWD"
export PYTHONDONTWRITEBYTECODE=1
export MIRA_FACE_MODEL_PATH="${MIRA_FACE_MODEL_PATH:-$PWD/public/models/face/face_landmarker.task}"
export MPLCONFIGDIR="$PWD/.runtime/matplotlib"
export MIRA_DATABASE_URL="${MIRA_DATABASE_URL:-sqlite:///$PWD/.runtime/mira_week1.db}"
exec .runtime/latest-backend-venv/bin/python -m uvicorn integration.app:app --host 127.0.0.1 --port 8000
