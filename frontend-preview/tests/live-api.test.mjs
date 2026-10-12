import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { apiConfig } from "../src/lib/config.ts";
import {
  getTutorial,
  getRecipeDTO,
  saveTutorialInput,
} from "../src/services/tutorial.ts";
import { getBeautyKit } from "../src/services/products.ts";
import { getMatchResult } from "../src/services/matching.ts";
import { getServiceStatus } from "../src/services/base.ts";
import { getCVAdaptation } from "../src/services/personalizedTutorial.ts";
import { setFaceConsent, setFaceProfileDTO } from "../src/services/face.ts";
const values = new Map();
globalThis.sessionStorage = {
  getItem: (k) => values.get(k) ?? null,
  setItem: (k, v) => values.set(k, String(v)),
  removeItem: (k) => values.delete(k),
};
const live = process.env.MIRA_LIVE_API === "1";
test(
  "live API: parse, retrieve, beauty kit, matching and CV passthrough",
  { skip: !live },
  async () => {
    Object.assign(apiConfig, {
      demoMode: false,
      mockFallback: false,
      baseUrl: "http://127.0.0.1:5173/api",
      exampleMediaPath: "data/input/main_eye_tutorial.mp4",
    });
    await saveTutorialInput({ kind: "example", name: "联调示例" });
    const actions = await getTutorial(),
      recipe = await getRecipeDTO();
    assert.equal(actions.length, 5);
    assert.equal(getServiceStatus("getTutorial").source, "api");
    const saved = await fetch(
      `${apiConfig.baseUrl}/recipes/${encodeURIComponent(recipe.recipe_id)}`,
    ).then((r) => r.json());
    assert.deepEqual(saved, recipe);
    const kit = await getBeautyKit();
    assert.equal(kit[0].productName, "大地色眼影盘");
    const matches = await getMatchResult();
    assert.deepEqual(
      matches.map((m) => m.actionId),
      actions.map((a) => a.id),
    );
    assert.ok(matches.every((m) => m.status === "missing"));
    const face = JSON.parse(
      readFileSync(
        new URL("./fixtures/face_profile_v0_3.json", import.meta.url),
      ),
    );
    setFaceConsent(true);
    setFaceProfileDTO(face);
    assert.deepEqual((await getCVAdaptation()).face_profile, face);
    setFaceConsent(false);
  },
);
test(
  "live API: missing saved recipe reparses instead of silently switching to mock",
  { skip: !live },
  async () => {
    await saveTutorialInput({ kind: "example", name: "恢复失效配方" });
    sessionStorage.setItem("mira-recipe-id", "missing-live-recipe");
    const actions = await getTutorial();
    assert.equal(actions.length, 5);
    assert.equal(getServiceStatus("getTutorial").source, "api");
  },
);

test(
  "live API: unavailable server keeps mock fallback enabled",
  { skip: !live },
  async () => {
    const base = apiConfig.baseUrl;
    try {
      apiConfig.baseUrl = "http://127.0.0.1:5173/unavailable-api";
      apiConfig.mockFallback = true;
      const products = await getBeautyKit();
      assert.ok(products.length);
      assert.equal(getServiceStatus("getBeautyKit").source, "mock-fallback");
    } finally {
      apiConfig.baseUrl = base;
    }
  },
);

test(
  "live personalization: recipe → synthetic v0.3 → API → My Tutorial context",
  { skip: !live },
  async () => {
    const { getPersonalizedTutorialContext } =
      await import("../src/services/personalizedTutorial.ts");
    const { toEngineRecipe } =
      await import("../src/services/adapters/personalization.ts");
    Object.assign(apiConfig, {
      demoMode: false,
      mockFallback: false,
      baseUrl: "http://127.0.0.1:5173/api",
      exampleMediaPath: "data/input/main_eye_tutorial.mp4",
    });
    await saveTutorialInput({
      kind: "example",
      name: "Personalization integration",
    });
    const profile = JSON.parse(
      readFileSync(
        new URL("./fixtures/face_profile_v0_3.json", import.meta.url),
      ),
    );
    try {
      setFaceConsent(true);
      setFaceProfileDTO(profile);
      const context = await getPersonalizedTutorialContext();
      const recipe = await getRecipeDTO();
      const response = await fetch(`${apiConfig.baseUrl}/personalization`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          face_profile: profile,
          standard_recipe: toEngineRecipe(recipe).standardRecipe,
          target_effect: "cat_eye",
        }),
      });
      assert.equal(response.status, 200);
      const raw = await response.json();
      assert.equal(context.actions.length, 5);
      assert.equal(
        context.provenance.actions,
        "backend-personalization/partial",
      );
      assert.equal(
        context.actions.filter(
          (a) => a.personalizationSource === "backend-personalization",
        ).length,
        1,
      );
      assert.deepEqual(
        context.actions[4].backendPersonalization,
        raw.personalized_actions[0],
      );
      assert.match(context.actions[4].personalized.direction, /12.60°/);
      assert.equal(getServiceStatus("getPersonalization").source, "api");
      profile.eye_geometry.eye_tail_angle.mean = 2;
      setFaceProfileDTO(profile);
      const changed = await getPersonalizedTutorialContext();
      assert.notDeepEqual(
        changed.actions[4].backendPersonalization.personalized_parameters,
        context.actions[4].backendPersonalization.personalized_parameters,
      );
      const base = apiConfig.baseUrl;
      apiConfig.mockFallback = true;
      const originalFetch = globalThis.fetch;
      try {
        globalThis.fetch = (url, options) =>
          originalFetch(
            String(url).endsWith("/personalization")
              ? `${base}/unavailable-personalization`
              : url,
            options,
          );
        const failed = await getPersonalizedTutorialContext();
        assert.equal(failed.provenance.actions, "mock/standard-fallback");
        assert.ok(failed.actions.every((a) => !a.backendPersonalization));
      } finally {
        globalThis.fetch = originalFetch;
      }
    } finally {
      setFaceConsent(false);
    }
  },
);

test(
  "live scan → aggregate v0.3 → personalization → My Tutorial, without injected profile",
  { skip: !live },
  async () => {
    const { scanFaceImages, getFaceProfileDTO } =
      await import("../src/services/face.ts");
    const { getPersonalizedTutorialContext } =
      await import("../src/services/personalizedTutorial.ts");
    Object.assign(apiConfig, {
      demoMode: false,
      mockFallback: false,
      baseUrl: "http://127.0.0.1:5173/api",
      exampleMediaPath: "data/input/main_eye_tutorial.mp4",
    });
    await saveTutorialInput({ kind: "example", name: "真实扫描链路验证" });
    const image = readFileSync(
      new URL("../public/assets/face/scan-guide.png", import.meta.url),
    );
    const original = globalThis.fetch;
    let submitted;
    try {
      const spec = await fetch(`${apiConfig.baseUrl}/openapi.json`).then((r) =>
        r.json(),
      );
      assert.ok(spec.paths["/face-scan"]);
      assert.ok(spec.paths["/personalization"]);
      globalThis.fetch = (url, options) => {
        if (String(url).endsWith("/personalization"))
          submitted = JSON.parse(options.body);
        return original(url, options);
      };
      setFaceConsent(true);
      const scan = await scanFaceImages(
        [1, 2, 3].map(() => new Blob([image], { type: "image/png" })),
      );
      assert.equal(scan.valid_frame_count, 3);
      assert.equal(scan.aggregated_face_profile.version, "0.3");
      assert.deepEqual(getFaceProfileDTO(), scan.aggregated_face_profile);
      const context = await getPersonalizedTutorialContext();
      assert.deepEqual(submitted.face_profile, scan.aggregated_face_profile);
      assert.equal(
        context.provenance.actions,
        "backend-personalization/partial",
      );
      assert.ok(
        context.actions.some(
          (a) => a.backendPersonalization?.personalized_parameters,
        ),
      );
      assert.equal(getServiceStatus("scanFaceImages").source, "api");
      assert.equal(getServiceStatus("getPersonalization").source, "api");
    } finally {
      globalThis.fetch = original;
      setFaceConsent(false);
    }
  },
);

test(
  "live personalization uses explicit mock v0.3 without requiring scan",
  { skip: !live },
  async () => {
    const { getPersonalizedTutorialContext } =
      await import("../src/services/personalizedTutorial.ts");
    Object.assign(apiConfig, {
      demoMode: false,
      mockFallback: false,
      baseUrl: "http://127.0.0.1:5173/api",
      exampleMediaPath: "data/input/main_eye_tutorial.mp4",
    });
    setFaceConsent(false);
    await saveTutorialInput({
      kind: "example",
      name: "无扫描 personalization 联调",
    });
    const context = await getPersonalizedTutorialContext();
    assert.equal(context.provenance.personalizationFace, "mock");
    assert.equal(context.provenance.actions, "backend-personalization/partial");
    assert.ok(context.actions.some((a) => a.adjustmentDetails?.length));
    assert.equal(getServiceStatus("getPersonalization").source, "api");
  },
);
test(
  "live special area preferences reach latest engine and tutorial context",
  { skip: !live },
  async () => {
    const { setLocalAppearancePreferences, clearLocalAppearancePreferences } =
      await import("../src/services/localAppearance.ts");
    const { getPersonalizedTutorialContext } =
      await import("../src/services/personalizedTutorial.ts");
    Object.assign(apiConfig, {
      demoMode: false,
      mockFallback: false,
      baseUrl: "http://127.0.0.1:5173/api",
    });
    setLocalAppearancePreferences([
      {
        id: "live-area",
        region: "局部区域",
        selection: { x: 0.5, y: 0.5, width: 0.2, height: 0.16 },
        preference: "soften",
        integrateStyle: null,
      },
    ]);
    try {
      const context = await getPersonalizedTutorialContext();
      assert.equal(
        context.localAppearanceGuidance[0].source,
        "backend-special-area",
      );
      assert.match(
        context.localAppearanceGuidance[0].instruction,
        /轻度均匀和边缘过渡/,
      );
      assert.equal(
        getServiceStatus("getLocalAppearanceGuidance").source,
        "api",
      );
    } finally {
      clearLocalAppearancePreferences();
    }
  },
);
