# Annie — MIRA Frontend Preview

This is a frontend prototype for preview only. Do not merge into main yet.

## Run locally

Node.js 22.12+ (or a compatible newer version) is recommended.

```sh
cd frontend-preview
npm install
npm run dev
```

Open http://127.0.0.1:5173 in your browser.

## Build

```sh
npm run build
```

## Scope

Standalone React / Vite / TypeScript frontend with Tailwind CSS, Radix UI, Framer Motion and Lucide React. It does not depend on the repository's existing Python code, database, or model files.

All AI, face analysis, product matching and coaching responses use predefined demo data. No real AI/CV, camera capture, microphone recognition, backend, account system or network upload is enabled. Missing technical imagery remains a placeholder. Existing editorial images and MIRA logos are included for visual preview only.

File and link inputs are local selections and do not upload data. Tutorial progress and consent choices use browser sessionStorage; saving a tutorial uses localStorage on the viewer's own browser. No browser storage exports or personal user data are included in this repository.

The preview supports both scanning (a clearly labelled example profile) and skipping scanning. The service / mock / type boundaries remain separate for future API integration.

This directory is isolated from the existing project. No changes to main or to other repository files are needed. Static hosting must fall back to index.html for client-side routes.
