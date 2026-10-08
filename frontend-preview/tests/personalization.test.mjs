import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { adaptPersonalizedTutorial } from "../src/services/adapters/personalizedTutorial.ts";
import { adaptRecipe } from "../src/services/adapters/tutorial.ts";
const recipe = JSON.parse(
  readFileSync(
    new URL(
      "../backend-reference/data/fixtures/standard_recipe_v1.json",
      import.meta.url,
    ),
  ),
);
test("personalization keeps arbitrary recipe step counts and never claims CV passthrough adapted actions", () => {
  const actions = adaptRecipe(recipe);
  const result = adaptPersonalizedTutorial(actions, true);
  assert.deepEqual(
    result.map((a) => a.actionId),
    actions.map((a) => a.id),
  );
  assert.equal(result[0].personalized.where, actions[0].area);
  assert.equal(result[0].personalizationSource, "mock/standard-fallback");
  assert.match(result[0].whyChanged, /基础位置/);
  assert.deepEqual(result[0].arGuidance.polygon, []);
});
