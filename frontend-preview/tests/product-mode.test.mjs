import test from "node:test";
import assert from "node:assert/strict";
import {
  clearProductUseMode,
  getProductUseMode,
  hasProductUseMode,
  resolveGenericProduct,
  setProductUseMode,
} from "../src/services/productMode.ts";
import { adaptPersonalizedTutorial } from "../src/services/adapters/personalizedTutorial.ts";
import { apiConfig } from "../src/lib/config.ts";
import { getPersonalizedTutorialContext } from "../src/services/personalizedTutorial.ts";
import { getFinishSummary } from "../src/services/finish.ts";
import { saveTutorialInput } from "../src/services/tutorial.ts";

const storage = () => {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
};

globalThis.sessionStorage = storage();

const action = (productRequirement, goal, name = "眼妆步骤") => ({
  id: "step-1",
  order: 1,
  name,
  area: "上眼睑",
  goal,
  productRequirement,
  tool: "晕染刷",
  motion: "轻扫",
  intensity: "轻",
  targetResult: "边缘自然",
  startTime: 0,
  endTime: 10,
});

test("product mode defaults safely to generic but preserves an explicit choice", () => {
  clearProductUseMode();
  assert.equal(hasProductUseMode(), false);
  assert.equal(getProductUseMode(), "generic");
  setProductUseMode("beauty-kit");
  assert.equal(hasProductUseMode(), true);
  assert.equal(getProductUseMode(), "beauty-kit");
  clearProductUseMode();
  assert.equal(hasProductUseMode(), false);
});

test("generic product labels describe category, colour and purpose", () => {
  assert.deepEqual(resolveGenericProduct(action("深棕色 · 哑光", "增加眼尾层次")), {
    label: "大地色眼影盘中的深棕色 / 加深色",
    source: "generic",
  });
  assert.equal(
    resolveGenericProduct(action("暖棕色 · 易晕染", "衔接深浅色")).label,
    "大地色眼影盘中的暖棕色 / 过渡色",
  );
  assert.equal(
    resolveGenericProduct(action("浅米色 · 哑光", "均匀眼皮底色")).label,
    "浅色哑光眼影 / 打底色",
  );
  assert.equal(
    resolveGenericProduct(action("香槟色 · 珠光", "中央提亮")).label,
    "浅色珠光眼影 / 提亮色",
  );
  assert.equal(
    resolveGenericProduct(action("哑光深色眼影", "加深外眼角")).label,
    "大地色眼影盘中的深棕色 / 加深色",
  );
  assert.equal(
    resolveGenericProduct(action("哑光过渡色眼影", "柔和眼窝边界")).label,
    "大地色眼影盘中的中棕色 / 过渡色",
  );
});

test("unknown requirements stay intact and are never turned into a product name", () => {
  assert.equal(
    resolveGenericProduct(action("透明定妆产品", "固定妆面")).label,
    "透明定妆产品",
  );
});

test("personalized actions use the resolved product consistently", () => {
  const original = action("深棕色 · 哑光", "增加眼尾层次");
  const result = adaptPersonalizedTutorial([original], false, [
    {
      actionId: original.id,
      label: "大地色眼影盘中的深棕色 / 加深色",
      source: "generic",
    },
  ]);
  assert.equal(result[0].product, "大地色眼影盘中的深棕色 / 加深色");
  assert.equal(result[0].productSource, "generic");
});

test("generic mode builds tutorial products without requesting a beauty kit or matching", async () => {
  setProductUseMode("generic");
  sessionStorage.setItem("mira-face", "false");
  apiConfig.demoMode = true;
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new Error("generic mode must not call the API");
  };
  try {
    const context = await getPersonalizedTutorialContext();
    assert.equal(context.productMode, "generic");
    assert.equal(context.actions[1].product, "冷调紫灰眼影中的深色 / 加深色");
    assert.equal(context.actions[1].productSource, "generic");
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = original;
    apiConfig.demoMode = false;
  }
});

test("generic mode finish summary does not claim product reuse or capability gaps", async () => {
  setProductUseMode("generic");
  sessionStorage.setItem("mira-face", "false");
  apiConfig.demoMode = true;
  try {
    const summary = await getFinishSummary();
    assert.equal(summary.productMode, "generic");
    assert.equal(summary.reused, 0);
    assert.deepEqual(summary.missing, []);
    assert.match(summary.productChange, /通用产品描述/);
  } finally {
    apiConfig.demoMode = false;
  }
});

test("starting a new tutorial clears the previous product choice", async () => {
  setProductUseMode("beauty-kit");
  await saveTutorialInput({ kind: "example", name: "新教程" });
  assert.equal(hasProductUseMode(), false);
  assert.equal(getProductUseMode(), "generic");
});
