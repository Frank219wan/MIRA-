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

## Latest scan preview

Scanning requires explicit consent before camera access or uploads. Browser-side input checks run locally using the bundled MediaPipe model and WASM assets in `public/models/face/` (about 37 MB). These are public runtime dependencies, not user face images. Real aggregation and personalization still require the compatible backend in API mode.

The countdown and capture tolerate brief blinking and minor movement, while sustained movement stops capture. These are conservative input checks, not an accuracy guarantee or comprehensive occlusion detection. See `docs/SCAN-QUALITY.md`.

Photo review is temporary. Users may separately opt in to keep numeric face profiles in the current browser session, and can clear them. Tutorial illustrations are generic closed-eyelid diagrams, not personal photo renderings.

## Personalization integration

`personalizationService` sends supported A02/A04 actions to `POST /personalization`, validates the response and normalizes it for My Tutorial. A measured v0.3 face profile takes priority; when absent, the bundled synthetic v0.3 fixture is explicitly labeled as demo input. API failures keep the existing fallback with diagnostic logging. Tutorial numeric parameters still use the documented cat-eye preset, not measurements extracted from the tutorial.
