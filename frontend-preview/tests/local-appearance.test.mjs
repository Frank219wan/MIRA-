import test from "node:test";
import assert from "node:assert/strict";
import {
  getLocalAppearancePreferences,
  setLocalAppearancePreferences,
  compileLocalAppearance,
} from "../src/services/localAppearance.ts";
import { saveTutorialInput } from "../src/services/tutorial.ts";
import {
  getPersonalizedTutorialContext,
  savePersonalizedTutorial,
} from "../src/services/personalizedTutorial.ts";
import { getSavedTutorials } from "../src/services/userCenter.ts";
import { apiConfig } from "../src/lib/config.ts";
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
test("preference validation, persistence and new tutorial reset", async () => {
  assert.throws(() =>
    setLocalAppearancePreferences([
      { region: "左脸颊", preference: "integrate", integrateStyle: null },
    ]),
  );
  const p = { region: "左脸颊", preference: "cover", integrateStyle: null };
  setLocalAppearancePreferences([p]);
  assert.deepEqual(getLocalAppearancePreferences(), [p]);
  await saveTutorialInput({ kind: "example", name: "新教程" });
  assert.deepEqual(getLocalAppearancePreferences(), []);
  sessionStorage.setItem("mira-local-appearance", "broken");
  assert.deepEqual(getLocalAppearancePreferences(), []);
});
test("all choices produce distinct authored guidance without inventing engine actions", () => {
  const eye = {
    id: "eye",
    area: "上眼睑",
    name: "眼线",
    productRequirement: "眼线笔",
  };
  const base = {
    id: "base",
    area: "全脸",
    name: "底妆",
    productRequirement: "粉底",
  };
  for (const preference of ["keep", "soften", "cover", "integrate"]) {
    const g = compileLocalAppearance(
      [
        {
          region: "左脸颊",
          preference,
          integrateStyle: preference === "integrate" ? "natural" : null,
        },
      ],
      [eye, base],
    )[0];
    assert.deepEqual(g.actionIds, ["base"]);
    assert.equal(g.source, "frontend-preference");
    assert.ok(g.instruction);
    assert.ok(g.stopWhen);
  }
  const p = {
    region: "眼周",
    preference: "integrate",
    integrateStyle: "highlight",
  };
  assert.deepEqual(compileLocalAppearance([p], [eye])[0].actionIds, []);
  assert.notEqual(
    compileLocalAppearance([p], [])[0].instruction,
    compileLocalAppearance([{ ...p, integrateStyle: "natural" }], [])[0]
      .instruction,
  );
});
test("tutorial and saved snapshot retain preferences without changing action count or backend payload", async () => {
  apiConfig.demoMode = true;
  try {
    setLocalAppearancePreferences([
      { region: "下巴", preference: "keep", integrateStyle: null },
    ]);
    const context = await getPersonalizedTutorialContext();
    assert.equal(context.actions.length, 5);
    assert.equal(context.localAppearanceGuidance.length, 1);
    assert.deepEqual(context.localAppearanceGuidance[0].actionIds, []);
    await savePersonalizedTutorial();
    assert.equal(
      getSavedTutorials()[0].localAppearanceGuidance[0].preference,
      "keep",
    );
  } finally {
    apiConfig.demoMode = false;
  }
});
