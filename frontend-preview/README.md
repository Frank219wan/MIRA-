# MIRA frontend preview

This is a frontend prototype for preview only. Do not merge into main yet.

```sh
cd frontend-preview
npm install
npm run dev
```

Use `npm run build` to build and `npm test` for frontend tests. Without an API, the frontend retains demo fallback. For local backend integration see `integration/README.md`. Local environment files, databases, captured photos and dependencies are excluded.

## Upload status

Images and videos can be uploaded to the local backend and previewed. Uploaded media has a dedicated parsing entry point, but a real vision provider is not configured yet. Parsing returns an explicit unavailable message instead of substituting demo results. API credentials are not included.
