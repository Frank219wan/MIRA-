import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  toEngineRecipe,
  applyPersonalization,
} from "../src/services/adapters/personalization.ts";
import { adaptRecipe } from "../src/services/adapters/tutorial.ts";
import { adaptPersonalizedTutorial } from "../src/services/adapters/personalizedTutorial.ts";
import { personalizeTutorialActions } from "../src/services/personalizedTutorial.ts";
import { setFaceConsent, setFaceProfileDTO } from "../src/services/face.ts";
import { saveTutorialInput } from "../src/services/tutorial.ts";
import { apiConfig } from "../src/lib/config.ts";
const fixture = (path) =>
  JSON.parse(readFileSync(new URL(path, import.meta.url)));
const recipe = fixture(
  "./fixtures/standard_recipe_v1.json",
);
const face = fixture("./fixtures/face_profile_v0_3.json");
const store = new Map();
globalThis.sessionStorage = {
  getItem: (k) => store.get(k) ?? null,
  setItem: (k, v) => store.set(k, v),
  removeItem: (k) => store.delete(k),
};
const fallback = () => adaptPersonalizedTutorial(adaptRecipe(recipe), true);
function response(mapping) {
  return {
    recipe_id: recipe.recipe_id,
    target_effect: "cat_eye",
    personalized_actions: mapping.standardRecipe.actions.map((a) => ({
      action_id: a.action_id,
      original_parameters: { ...a.parameters },
      personalized_parameters: { ...a.parameters, direction_angle_deg: 13 },
      applied_rules: ["R01"],
      adjustments: [
        {
          rule_ids: ["R01"],
          feature_path: "eye_geometry.eye_tail_angle.mean",
          feature_value: 8.5,
          parameter: "direction_angle_deg",
          operation: "add",
          adjustment_value: 3,
          original_value: 10,
          personalized_value: 13,
        },
      ],
    })),
  };
}
test("maps semantic eyeliner only, never maps step 2 to A02; supports repeated genuine lower-lid actions", () => {
  const mapped = toEngineRecipe(recipe);
  assert.deepEqual(
    mapped.standardRecipe.actions.map((a) => a.action_id),
    ["A04"],
  );
  assert.deepEqual(mapped.tutorialActionIds, [`${recipe.recipe_id}:5`]);
  assert.equal(mapped.parameterSource, "frontend-demo-baseline");
  const lower = {
    ...recipe.action_units[0],
    area: "lower eyelid",
    product_requirement: "matte shadow",
  };
  assert.deepEqual(
    toEngineRecipe({
      ...recipe,
      action_units: [
        { ...lower, step_index: 1 },
        { ...lower, step_index: 2 },
      ],
    }).standardRecipe.actions.map((a) => a.action_id),
    ["A02", "A02"],
  );
});
test("merges engine values into original step identity and retains unadapted steps and raw adjustments", () => {
  const mapping = toEngineRecipe(recipe),
    raw = response(mapping),
    before = fallback();
  const result = applyPersonalization(before, mapping, raw);
  assert.equal(result.length, 5);
  assert.deepEqual(result.slice(0, 4), before.slice(0, 4));
  assert.equal(result[4].personalizationSource, "backend-personalization");
  assert.match(result[4].personalized.direction, /13.00°/);
  assert.deepEqual(
    result[4].backendPersonalization,
    raw.personalized_actions[0],
  );
  assert.deepEqual(result[4].arGuidance, before[4].arGuidance);
  for (const corrupt of [
    { ...raw, recipe_id: "wrong" },
    { ...raw, personalized_actions: [] },
    {
      ...raw,
      personalized_actions: [
        { ...raw.personalized_actions[0], action_id: "A02" },
      ],
    },
    {
      ...raw,
      personalized_actions: [
        {
          ...raw.personalized_actions[0],
          personalized_parameters: { direction_angle_deg: NaN },
        },
      ],
    },
  ]) {
    assert.throws(() => applyPersonalization(before, mapping, corrupt));
  }
});
test("missing face uses marked mock v0.3; API failure preserves fallback and respects disabled fallback", async () => {
  const original = globalThis.fetch;
  Object.assign(apiConfig, {
    demoMode: false,
    mockFallback: true,
    exampleMediaPath: "demo.mp4",
  });
  try {
    await saveTutorialInput({
      kind: "example",
      name: "mock profile integration",
    });
    setFaceConsent(false);
    let sent;
    globalThis.fetch = async (url, options) => {
      if (String(url).endsWith("/personalization")) {
        sent = JSON.parse(options.body);
        return Response.json(response(toEngineRecipe(recipe)));
      }
      return Response.json(recipe);
    };
    const personalized = await personalizeTutorialActions(fallback());
    assert.equal(sent.face_profile.version, "0.3");
    assert.equal(personalized[4].faceProfileSource, "mock");
    assert.equal(
      personalized[4].personalizationSource,
      "backend-personalization",
    );
    assert.ok(personalized[4].adjustmentDetails.length);
    await saveTutorialInput({ kind: "example", name: "test" });
    setFaceConsent(true);
    setFaceProfileDTO(face);
    globalThis.fetch = async (url) =>
      String(url).endsWith("/personalization")
        ? new Response("{}", { status: 503 })
        : new Response(JSON.stringify(recipe));
    assert.deepEqual(await personalizeTutorialActions(fallback()), fallback());
    apiConfig.mockFallback = false;
    await assert.rejects(personalizeTutorialActions(fallback()));
  } finally {
    globalThis.fetch = original;
    setFaceConsent(false);
  }
});
