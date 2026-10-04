# MIRA frontend preview

This is a frontend prototype for preview only. Do not merge into main yet.

## Run locally

```bash
cd frontend-preview
npm install
npm run dev
```

Open the local URL printed by Vite (normally http://127.0.0.1:5173).
Requires Node.js 22.12+ or a compatible newer version.

```bash
npm run build
```

## Data and optional backend connection

The default preview uses bundled mock data. No backend, database, credentials, or personal face profiles are included. Face scanning requires a compatible backend; in this standalone preview you can skip scanning and continue with the standard tutorial.

To connect an independently running compatible backend at http://127.0.0.1:8000:

```bash
VITE_DEMO_MODE=false VITE_MOCK_FALLBACK=true npm run dev
```

Vite proxies `/api` to that backend. The services support `/tutorials/parse`, `/recipes/:id`, `/beauty-kit`, `/matching`, `/cv-adaptation`, `/face-scan`, and `/personalization`. Parsing currently requires a server-side media path; configure `VITE_EXAMPLE_MEDIA_PATH` and `VITE_EXAMPLE_MEDIA_KIND` for a sample available on that backend. Backend availability and implemented capabilities determine which results are real; unavailable features retain fallback data.

Face images are submitted only for an explicitly requested scan in API mode. Backend-derived personalization is identified separately from fallback. The backend currently used by this prototype supports personalization for A02/A04; other steps retain their standard or fallback guidance.

Only frontend runtime source, static display assets, package manifests, and build configuration are included here. Backend code and documentation remain untouched.
