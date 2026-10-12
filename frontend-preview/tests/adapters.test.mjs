import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { adaptRecipe } from "../src/services/adapters/tutorial.ts";
import { adaptBeautyKit } from "../src/services/adapters/beautyKit.ts";
import { adaptMatching } from "../src/services/adapters/matching.ts";
import { adaptFaceProfile } from "../src/services/adapters/face.ts";
const fixture = (name) =>
  JSON.parse(
    readFileSync(
      new URL(
        `../backend-reference/data/fixtures/${name}.json`,
        import.meta.url,
      ),
    ),
  );
const frontendFixture = (name) =>
  JSON.parse(
    readFileSync(new URL(`./fixtures/${name}.json`, import.meta.url)),
  );
const recipe = fixture("standard_recipe_v1");
test("recipe preserves step identity, timestamps and generates labels", () => {
  const result = adaptRecipe(recipe);
  assert.equal(result.length, recipe.action_units.length);
  assert.equal(result[0].id, `${recipe.recipe_id}:1`);
  assert.ok(result[0].name);
  assert.equal(result[0].productRequirement, "眼部打底产品");
  const unit = { ...recipe.action_units[0], time_range_seconds: [2.5, 8] };
  assert.equal(adaptRecipe({ ...recipe, action_units: [unit] })[0].endTime, 8);
  assert.equal(
    adaptRecipe({
      ...recipe,
      action_units: [{ ...unit, time_range_seconds: null }],
    })[0].startTime,
    0,
  );
  assert.throws(() => adaptRecipe({ ...recipe, action_units: [] }));
});
test("kit retains backend identities and never borrows shades for unknown products", () => {
  const kit = fixture("beauty_kit_v1");
  const result = adaptBeautyKit(kit);
  assert.equal(result[0].id, kit.products[0].product_id);
  assert.ok(result[0].shades.length);
  assert.deepEqual(
    adaptBeautyKit({
      ...kit,
      products: [
        { product_id: "unknown", name: "Unknown", capability_ids: ["x"] },
      ],
    })[0].shades,
    [],
  );
});
test("matching aligns by step index and marks unsupported metrics as fallback", () => {
  const kit = fixture("beauty_kit_v1");
  const result = adaptMatching(
    {
      recipe_id: recipe.recipe_id,
      beauty_kit_id: kit.kit_id,
      items: [
        {
          step_index: 1,
          status: "substitution_candidate",
          product_id: kit.products[0].product_id,
        },
      ],
    },
    recipe,
    adaptBeautyKit(kit),
  );
  assert.equal(result[0].status, "partial");
  assert.equal(result[0].actionId, adaptRecipe(recipe)[0].id);
  assert.equal(result[0].provenance.score, "frontend-fallback");
  assert.deepEqual(result[0].capabilityChecks, []);
  assert.equal(result.length, recipe.action_units.length);
  assert.equal(result[1].status, "missing");
});
test("face preserves geometry units and explicitly separates mock color analysis", () => {
  const dto = frontendFixture("face_profile_v0_3");
  const result = adaptFaceProfile(dto);
  assert.ok(result.profile.structure.some((x) => x.value.includes("8.50°")));
  assert.equal(result.provenance.color, "mock");
  assert.equal(result.provenance.geometry, "face-profile");
  assert.throws(() => adaptFaceProfile({ ...dto, version: "9" }));
});
