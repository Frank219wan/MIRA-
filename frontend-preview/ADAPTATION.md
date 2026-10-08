# Frontend API adaptation

The UI domain types are unchanged. Pages call services; services retain backend DTOs, send them to the API, and map responses into the existing page models. `backend-reference/` is read-only and was not modified.

## Run modes

Copy `.env.example` to `.env.local` and restart Vite after changing values.

- Default: `VITE_DEMO_MODE=true`. All existing offline demo interactions work without a backend.
- API with fallback: `VITE_DEMO_MODE=false`, `VITE_MOCK_FALLBACK=true`.
- Strict integration: set both flags to `false`. HTTP/network/validation failures reach the page error state instead of returning mock data.
- `VITE_API_BASE_URL=/api`: development proxy targets `http://127.0.0.1:8000`. Production/preview requires a reverse proxy or an API URL with CORS configured by the hosting environment. The frontend does not change backend settings.
- Timeout: `VITE_API_TIMEOUT_MS=30000`.
- Set `VITE_EXAMPLE_MEDIA_PATH` to a path readable by the backend and `VITE_EXAMPLE_MEDIA_KIND` to `video` or `frame_directory`.

The existing backend accepts a JSON media reference, not multipart upload or remote tutorial URLs. The current file/link UI still only stores its selection and falls back explicitly. With fallback disabled, unsupported input produces an error. Future upload integration should call `parseTutorial({media_path, media_kind, recipe_id, title})` once it has a server path. No filenames or links are silently presented as uploaded media.

## Mapping and provenance

- `tutorial`: synchronous POST `/tutorials/parse`; GET `/recipes/:id` after a reload with a saved ID, plus an explicit `getRecipe(id)` service. Concurrent callers share one parse request. New input clears the recipe and completed-step state. Action IDs are `${recipe_id}:${step_index}`. Missing step names are generated from goal and area; unavailable timestamps use `0/0`, never invented durations. The animated parsing stages remain a visual demo and cannot finish before the recipe returns.
- `beauty kit`: preserves backend product IDs/names. Explicit ID-based metadata joins add existing demo palette shades/brand/image/category. Unknown products get no invented shades, a missing-brand label, and the current eye-oriented UI category fallback. `productMetadataSource(id)` exposes the metadata origin. Capability IDs remain in the retained DTO.
- `matching`: POST `{recipe, beauty_kit}` using original transport DTOs. Results align by `step_index`, not response array position. Status mapping is `matched → matched`, `unmatched → missing`, `substitution_candidate → partial`. Unsupported score is internally `0` for domain compatibility, with `provenance.score=frontend-fallback`; the page renders “未提供”. Capability checks and missing capability details are empty when not evaluated. Backend notes remain separately identified. Missing response items become explicitly marked frontend fallback rows. API failures never attach unrelated mock products to real actions by index.
- `face`: no face acquisition endpoint exists in the supplied backend. After consent, CV integration calls `setFaceProfileDTO(v01Payload)`. Numeric geometry is validated and converted into ratio, degree and percentage labels. `getFaceProfileContext()` separates real geometry from mock color analysis. Color fields always remain mock. Raw profile data stays in memory and is cleared when consent is revoked; reload requires re-injection.
- `personalizedTutorial`: `getPersonalizedTutorialContext()` returns actions, face context, `/cv-adaptation` response and provenance. Only an injected real profile is sent to CV. The backend currently only validates/returns geometry, so this is labeled `backend-passthrough`, not a generated adaptation. Existing demo actions are preserved for matching demo IDs. New recipe IDs receive standard-direction fallback actions with no invented AR polygons. Replace the action adapter when a real per-step adaptation contract exists.
- `base/client`: centralized JSON requests, timeouts and structured API errors (`status`, `code`, `requestId`). `getServiceStatus(name)` records demo/API/fallback/error provenance; fallback emits a diagnostic warning and participating pages show a short notice. Stable status keys survive minification. Coach and scan quality remain explicit mock-only features even in API mode.

## Files

New:
- `src/services/api/dto.ts`, `src/services/api/client.ts`
- `src/services/adapters/tutorial.ts`, `beautyKit.ts`, `matching.ts`, `face.ts`, `personalizedTutorial.ts`
- `.env.example`
- `tests/register.mjs`, `tests/adapters.test.mjs`, `tests/services.test.mjs`, `tests/personalization.test.mjs`
- `ADAPTATION.md`

Updated:
- `src/lib/config.ts`
- `src/services/base.ts`, `tutorial.ts`, `products.ts`, `matching.ts`, `face.ts`, `personalizedTutorial.ts`, `finish.ts`
- `src/hooks/useService.ts`
- `src/pages/Parsing.tsx`, `Matching.tsx`, `BeautyKit.tsx`, `BeautyProfile.tsx`, `MyTutorial.tsx`, `LiveCoach.tsx`
- `vite.config.ts`, `package.json`, `README.md`

Build output under `dist/` and TypeScript build information are regenerated by the build. No new dependencies, CSS changes, or domain type changes.

## Verification

`npm test`: 10 passing tests using Node's test runner and the checked-in backend JSON fixtures. Covers recipe timestamps/validation, stable IDs, metadata identity, missing matching metrics, geometry provenance, arbitrary recipe action mapping, structured error/fallback policy, parse deduplication, request envelopes, encoded recipe retrieval, timeout, CV payload and consent revocation. Tests require a modern Node with native TypeScript stripping and `module.registerHooks` (tested on Node 26.8.2).

`npm run build`: TypeScript and Vite production build pass. Vite reports one non-blocking warning for the approximately 504 kB main JS chunk (approximately 164 kB gzip).

HTTP boundary unit tests intercept `fetch`. Real backend and browser integration were subsequently completed; see `INTEGRATION.md`. The Week 1 matching/CV endpoints still have their original placeholder semantics.
