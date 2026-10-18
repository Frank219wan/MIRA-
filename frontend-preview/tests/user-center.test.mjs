import test from "node:test";
import assert from "node:assert/strict";
const values = new Map();
globalThis.localStorage = {
  getItem: (k) => values.get(k) ?? null,
  setItem: (k, v) => values.set(k, String(v)),
  removeItem: (k) => values.delete(k),
};
test("collection migrates previous save, keeps multiple recipes and replaces duplicate IDs", async () => {
  const service = await import("../src/services/userCenter.ts");
  values.set(
    "mira-saved-tutorial",
    JSON.stringify({
      savedAt: "2026-10-05",
      actions: [{ actionId: "old:1", instructions: "轻扫" }],
      productMode: "generic",
    }),
  );
  assert.equal(service.getSavedTutorials().length, 1);
  service.storeTutorial({
    id: "new",
    title: "新教程",
    savedAt: "2026-10-05",
    actions: [{ actionId: "new:1", instructions: "轻扫" }],
  });
  assert.equal(service.getSavedTutorials().length, 2);
  service.storeTutorial({
    id: "new",
    title: "新教程更新",
    savedAt: "2026-10-05",
    actions: [{ actionId: "new:1", instructions: "轻扫" }],
  });
  assert.equal(service.getSavedTutorials().length, 2);
  service.removeTutorial("new");
  assert.equal(service.getSavedTutorials().length, 1);
  values.set("mira-tutorials", "bad");
  assert.deepEqual(service.getSavedTutorials(), []);
});
