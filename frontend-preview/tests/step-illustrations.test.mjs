import test from "node:test";
import assert from "node:assert/strict";
import { guideKindFor } from "../src/components/coach/stepIllustrationModel.ts";

const action = (name, area, productRequirement) => ({
  id: name,
  order: 1,
  name,
  area,
  goal: "",
  productRequirement,
  tool: "",
  motion: "",
  intensity: "",
  targetResult: "",
  startTime: 0,
  endTime: 0,
});

test("the canonical five eye steps use five distinct guide geometries", () => {
  const kinds = [
    guideKindFor(action("眼皮打底", "整个上眼睑", "浅米色 · 哑光")),
    guideKindFor(action("加深眼尾", "外眼角 1/3", "深棕色 · 哑光")),
    guideKindFor(action("中央提亮", "上眼睑中央", "香槟色 · 珠光")),
    guideKindFor(action("下眼影", "下睫毛根部", "棕色 · 哑光")),
    guideKindFor(action("描画眼线", "上睫毛根部", "深棕色 · 眼线")),
  ];
  assert.deepEqual(kinds, ["base", "outer", "highlight", "lower", "liner"]);
  assert.equal(new Set(kinds).size, 5);
});
