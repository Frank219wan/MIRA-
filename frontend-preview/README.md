# MIRA Frontend Preview

This is a frontend prototype for preview only. Do not merge into main yet.

## Run locally

```sh
cd frontend-preview
npm install
npm run dev
```

Open http://127.0.0.1:5173.

The checked-in configuration defaults to offline demo data, so the preview runs without a backend or private environment variables.

## Optional API integration

Copy `.env.example` to `.env.local` and use:

```env
VITE_DEMO_MODE=false
VITE_MOCK_FALLBACK=true
VITE_API_BASE_URL=/api
VITE_API_TIMEOUT_MS=30000
```

During local development, Vite proxies `/api` to `http://127.0.0.1:8000`. Keep `VITE_MOCK_FALLBACK=true` when the backend is unavailable or still returns placeholder results.

## Build

```sh
npm install
npm run build
```
