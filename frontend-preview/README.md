# MIRA frontend preview

This is a frontend prototype for preview only. Do not merge into main yet.

```sh
cd frontend-preview
npm install
npm run dev
```

Use `npm run build` to build and `npm test` for frontend tests. Without an API, the frontend retains demo fallback. For local backend integration see `integration/README.md`. Local environment files, databases, captured photos and dependencies are excluded.

## GitHub Pages demo

The static Pages build is intentionally separate from local API development:

```sh
cd frontend-preview
npm ci
npm test
npm run build:pages
npm run preview:pages
```

`build:pages` uses the `/MIRA-/` Vite base and enables the clearly labelled
frontend demo mode. Routing uses URL hashes, so direct links such as
`https://frank219wan.github.io/MIRA-/#/beauty-kit` survive refreshes without a
server-side SPA rewrite. The workflow in `.github/workflows/deploy-pages.yml`
checks pull requests and deploys only merged `main` builds.

The Pages site does not run FastAPI. The authored example tutorial, product
catalogue, explicitly labelled matching fixtures, manual special-area
preferences and Live Coach illustrations remain available. Custom tutorial
upload/parsing, server-generated Face Profile values, backend personalization
and server guidance require the local API. Camera/photo frames used for the
scan pre-check stay in the browser in Pages mode and are not sent to a public
fallback endpoint.

## Upload status

Images and videos can be uploaded to the local backend and previewed. Uploaded media has a dedicated parsing entry point, but a real vision provider is not configured yet. Parsing returns an explicit unavailable message instead of substituting demo results. API credentials are not included.
