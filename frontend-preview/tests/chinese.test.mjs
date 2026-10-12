import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { adaptRecipe } from "../src/services/adapters/tutorial.ts";
import { adaptMatching } from "../src/services/adapters/matching.ts";
import { adaptBeautyKit } from "../src/services/adapters/beautyKit.ts";
const fixture = (name) =>
  JSON.parse(
    readFileSync(
      new URL(
        `../backend-reference/data/fixtures/${name}.json`,
        import.meta.url,
      ),
    ),
  );
test("real tutorial fields and generated names display Chinese without changing transport DTO", () => {
  const dto = fixture("standard_recipe_v1");
  const raw = JSON.stringify(dto);
  const actions = adaptRecipe(dto);
  for (const action of actions)
    for (const key of [
      "name",
      "area",
      "goal",
      "productRequirement",
      "tool",
      "motion",
      "intensity",
      "targetResult",
    ])
      assert.doesNotMatch(action[key], /[a-z]/i, key);
  assert.equal(JSON.stringify(dto), raw);
});
test("backend products and placeholder explanations display Chinese", () => {
  const kit = fixture("beauty_kit_v1"),
    recipe = fixture("standard_recipe_v1");
  assert.equal(adaptBeautyKit(kit)[0].productName, "大地色眼影盘");
  const rows = adaptMatching(
    {
      recipe_id: recipe.recipe_id,
      items: [
        {
          step_index: 1,
          status: "unmatched",
          note: "Week 1 structural placeholder; no matching algorithm executed.",
        },
      ],
    },
    recipe,
    [],
  );
  assert.doesNotMatch(rows[0].difference, /[a-z]/i);
});
