import test from "node:test";
import assert from "node:assert/strict";
import { apiConfig } from "../src/lib/config.ts";
import { request, ApiError } from "../src/services/api/client.ts";
import { withFallback, getServiceStatus } from "../src/services/base.ts";
import { readFileSync } from "node:fs";
const fixture = (name) =>
  JSON.parse(
    readFileSync(
      new URL(
        `./fixtures/${name}.json`,
        import.meta.url,
      ),
    ),
  );
const storage = () => {
  const m = new Map();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
  };
};
globalThis.sessionStorage = storage();
globalThis.localStorage = storage();
test("client reports structured backend errors and fallback can be disabled", async () => {
  apiConfig.demoMode = false;
  const original = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        error: { code: "invalid_request_payload", message: "Bad input" },
        request_id: "req-1",
      }),
      { status: 422 },
    );
  try {
    await assert.rejects(
      request("/matching"),
      (e) =>
        e instanceof ApiError &&
        e.code === "invalid_request_payload" &&
        e.requestId === "req-1",
    );
    apiConfig.mockFallback = true;
    assert.equal(
      await withFallback(
        "test",
        () => request("/x"),
        () => "demo",
      ),
      "demo",
    );
    assert.equal(getServiceStatus("test").source, "mock-fallback");
    apiConfig.mockFallback = false;
    await assert.rejects(
      withFallback(
        "test",
        () => request("/x"),
        () => "demo",
      ),
    );
  } finally {
    globalThis.fetch = original;
    apiConfig.mockFallback = true;
  }
});
test("parse is deduplicated and matching sends original DTO envelopes", async () => {
  const { saveTutorialInput, getTutorial } =
    await import("../src/services/tutorial.ts");
  const { getMatchResult } = await import("../src/services/matching.ts");
  const recipe = fixture("standard_recipe_v1"),
    kit = fixture("beauty_kit_v1");
  apiConfig.demoMode = false;
  apiConfig.mockFallback = false;
  apiConfig.exampleMediaPath = "/server/demo.mp4";
  const calls = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    calls.push([url, init?.body && JSON.parse(init.body)]);
    const body = String(url).endsWith("/tutorials/parse")
      ? recipe
      : String(url).endsWith("/beauty-kit")
        ? kit
        : {
            recipe_id: recipe.recipe_id,
            beauty_kit_id: kit.kit_id,
            items: recipe.action_units.map((a) => ({
              step_index: a.step_index,
              status: "unmatched",
            })),
          };
    return new Response(JSON.stringify(body), { status: 200 });
  };
  try {
    await saveTutorialInput({ kind: "example", name: "Example" });
    const [a, b] = await Promise.all([getTutorial(), getTutorial()]);
    assert.deepEqual(a, b);
    assert.equal(
      calls.filter(([u]) => u.endsWith("/tutorials/parse")).length,
      1,
    );
    const matches = await getMatchResult();
    assert.equal(matches[0].actionId, a[0].id);
    const payload = calls.find(([u]) => u.endsWith("/matching"))[1];
    assert.deepEqual(payload.recipe, recipe);
    assert.deepEqual(payload.beauty_kit, kit);
    await saveTutorialInput({
      kind: "link",
      name: "https://example.com/video",
    });
    await assert.rejects(getTutorial(), /服务器媒体路径/);
  } finally {
    globalThis.fetch = original;
  }
});
test("recipe retrieval uses encoded id and invalidates previous parse cache", async () => {
  const { saveTutorialInput, getRecipeDTO } =
    await import("../src/services/tutorial.ts");
  const original = globalThis.fetch;
  let requested;
  try {
    await saveTutorialInput({ kind: "example", name: "New" });
    sessionStorage.setItem("mira-recipe-id", "saved/id");
    globalThis.fetch = async (url) => {
      requested = url;
      return new Response(JSON.stringify(fixture("standard_recipe_v1")));
    };
    await getRecipeDTO();
    assert.ok(requested.endsWith("/recipes/saved%2Fid"));
  } finally {
    globalThis.fetch = original;
  }
});
test("client timeout has an identifiable error code", async () => {
  const original = globalThis.fetch,
    timeout = apiConfig.timeoutMs;
  try {
    apiConfig.timeoutMs = 5;
    globalThis.fetch = async (_url, init) =>
      new Promise((_, reject) =>
        init.signal.addEventListener("abort", () =>
          reject(new Error("aborted")),
        ),
      );
    await assert.rejects(request("/slow"), (e) => e.code === "timeout");
  } finally {
    globalThis.fetch = original;
    apiConfig.timeoutMs = timeout;
  }
});
test("real face handoff sends v0.3 unchanged and consent revocation clears it", async () => {
  const { setFaceConsent, setFaceProfileDTO, getFaceProfileDTO } =
    await import("../src/services/face.ts");
  const { getCVAdaptation } =
    await import("../src/services/personalizedTutorial.ts");
  const face = JSON.parse(
    readFileSync(
      new URL("./fixtures/face_profile_v0_3.json", import.meta.url),
    ),
  );
  const original = globalThis.fetch;
  let body;
  apiConfig.demoMode = false;
  apiConfig.mockFallback = false;
  try {
    setFaceConsent(false);
    assert.throws(() => setFaceProfileDTO(face));
    setFaceConsent(true);
    setFaceProfileDTO(face);
    globalThis.fetch = async (_url, init) => {
      body = JSON.parse(init.body);
      return new Response(
        JSON.stringify({
          schema_version: "1.0",
          recipe_id: body.recipe.recipe_id,
          face_profile: body.face_profile,
        }),
      );
    };
    const result = await getCVAdaptation();
    assert.deepEqual(body.face_profile, face);
    assert.deepEqual(result.face_profile, face);
    setFaceConsent(false);
    assert.equal(getFaceProfileDTO(), undefined);
    assert.equal(await getCVAdaptation(), null);
  } finally {
    globalThis.fetch = original;
    setFaceConsent(false);
  }
});
