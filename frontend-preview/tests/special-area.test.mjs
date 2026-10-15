import { test } from "node:test";
import assert from "node:assert/strict";
import {
  toSpecialAreaProfile,
  normalizeSpecialAreaGuidance,
  getLocalAppearanceGuidance,
} from "../src/services/specialAreaService.ts";
import { compileLocalAppearance } from "../src/services/localAppearance.ts";
const prefs = ["keep", "soften", "cover", "integrate"].map((preference, i) => ({
  id: `area-${i}`,
  region: "局部区域",
  selection: { x: 0.1, y: 0.08, width: 0.2, height: 0.16 },
  preference,
  integrateStyle: preference === "integrate" ? "highlight" : null,
}));
test("special area maps supported preferences and bounded ellipse without images or inferred labels", () => {
  const p = toSpecialAreaProfile(prefs);
  assert.deepEqual(
    p.areas.map((a) => a.preference),
    ["KEEP", "BLEND", "COVER"],
  );
  assert.ok(
    p.areas.every(
      (a) =>
        a.polygon.length === 16 &&
        a.polygon.every((pt) =>
          Object.values(pt).every((v) => v >= 0 && v <= 1),
        ) &&
        a.location === "other" &&
        a.user_label === "",
    ),
  );
});
test("backend guidance replaces only matched instructions and retains integration fallback", () => {
  const p = toSpecialAreaProfile(prefs),
    local = compileLocalAppearance(prefs, []);
  const dto = {
    schema_version: "0.1",
    image_sample_id: p.image_sample_id,
    tutorial_type: "complexion_base_makeup",
    guidance_blocks: p.areas.map((a) => ({
      area_id: a.area_id,
      preference: a.preference,
      decision_source: "user_preference",
      guidance_zh: "后端指导",
    })),
  };
  const result = normalizeSpecialAreaGuidance(dto, p, local);
  assert.equal(result[0].source, "backend-special-area");
  assert.equal(result[0].instruction, "后端指导");
  assert.deepEqual(result[3], local[3]);
  assert.throws(() =>
    normalizeSpecialAreaGuidance(
      {
        ...dto,
        guidance_blocks: [
          dto.guidance_blocks[0],
          dto.guidance_blocks[0],
          dto.guidance_blocks[0],
        ],
      },
      p,
      local,
    ),
  );
  assert.throws(() =>
    normalizeSpecialAreaGuidance(
      { ...dto, image_sample_id: "other" },
      p,
      local,
    ),
  );
});
test("empty preferences never call API", async () => {
  assert.deepEqual(await getLocalAppearanceGuidance([], []), []);
});
test("service uses backend and falls back diagnostically on failure", async () => {
  const { apiConfig } = await import("../src/lib/config.ts");
  const { getServiceStatus } = await import("../src/services/base.ts");
  const oldFetch = globalThis.fetch,
    config = { ...apiConfig };
  try {
    Object.assign(apiConfig, { demoMode: false, mockFallback: true });
    globalThis.fetch = async (_url, options) => {
      const { profile } = JSON.parse(options.body);
      return new Response(
        JSON.stringify({
          schema_version: "0.1",
          image_sample_id: profile.image_sample_id,
          tutorial_type: "complexion_base_makeup",
          guidance_blocks: profile.areas.map((a) => ({
            area_id: a.area_id,
            preference: a.preference,
            decision_source: "user_preference",
            guidance_zh: "真实服务指导",
          })),
        }),
        { status: 200 },
      );
    };
    assert.equal(
      (await getLocalAppearanceGuidance(prefs, []))[0].source,
      "backend-special-area",
    );
    globalThis.fetch = async () => new Response("{}", { status: 503 });
    assert.equal(
      (await getLocalAppearanceGuidance(prefs, []))[0].source,
      "frontend-preference",
    );
    assert.equal(
      getServiceStatus("getLocalAppearanceGuidance").source,
      "mock-fallback",
    );
  } finally {
    globalThis.fetch = oldFetch;
    Object.assign(apiConfig, config);
  }
});

test("user-selected location and label reach backend unchanged", () => {
 const area = toSpecialAreaProfile([{...prefs[0], region: "左脸颊", userLabel: "我的标记"}]).areas[0];
 assert.equal(area.location, "subject_left_cheek");
 assert.equal(area.user_label, "我的标记");
});
