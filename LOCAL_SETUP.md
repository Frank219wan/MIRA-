# MIRA local setup

This checkout runs the current integrated review branch: React/Vite at
`127.0.0.1:5173` and FastAPI/SQLite/MediaPipe at `127.0.0.1:8000`.

## First-time setup

```sh
cd /Users/wansiyu/Documents/ChatGPT/欧莱雅/MIRA-latest
python3 -m venv frontend-preview/.runtime/latest-backend-venv
frontend-preview/.runtime/latest-backend-venv/bin/python -m pip install --upgrade pip
frontend-preview/.runtime/latest-backend-venv/bin/python -m pip install \
  -r requirements.txt \
  -r frontend-preview/integration/requirements.txt \
  -c frontend-preview/integration/constraints.txt
cd frontend-preview && npm ci && cd ..
```

The local `.env.local` sets `VITE_DEMO_MODE=false`, so implemented services call
the local API. Mock fallback remains enabled for UI modules that have no real
provider yet. No API key is required for the implemented local flow.

## Start

```sh
cd /Users/wansiyu/Documents/ChatGPT/欧莱雅/MIRA-latest
./scripts/start-local.sh
```

On macOS the script opens <http://127.0.0.1:5173> after both services are
reachable. Set `MIRA_NO_BROWSER=1` before the command to skip opening a browser.
API health is available at
<http://127.0.0.1:8000/health>.

## Tests

```sh
cd /Users/wansiyu/Documents/ChatGPT/欧莱雅/MIRA-latest
frontend-preview/.runtime/latest-backend-venv/bin/python -m pytest -q tests
PYTHONPATH="$PWD:$PWD/frontend-preview" \
  frontend-preview/.runtime/latest-backend-venv/bin/python -m pytest -q \
  frontend-preview/integration
cd frontend-preview && npm test && npm run build
```

Uploaded media is local-only. Face scan uploads are processed in memory; tutorial
preview uploads use the system temporary directory and expire. Keep personal
photos out of Git-tracked paths.
