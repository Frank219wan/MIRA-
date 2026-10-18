import { actions } from "./tutorial";
import { products } from "./products";
import type { MatchResult } from "../types/matching";
export const matches: MatchResult[] = actions.map((a, i) => ({
  actionId: a.id,
  status: i === 2 ? "missing" : i === 1 ? "partial" : "matched",
  bestMatch: products[0],
  score: i === 2 ? 32 : i === 1 ? 78 : 94,
  capabilityChecks: [
    { label: i === 2 ? "香槟色" : "所需色系", passed: true },
    { label: i === 2 ? "珠光质地" : "哑光质地", passed: i !== 2 },
    { label: i === 2 ? "高反光能力" : "易于晕染", passed: i !== 2 },
  ],
  reason: "演示数据，仅用于后端不可用时展示界面。",
  difference:
    i === 2
      ? "颜色相近，但质地功能不同"
      : i === 1
        ? "暖棕色略深，用量需要减少"
        : "颜色与质地符合本步骤需求",
  impact:
    i === 2
      ? "可以保留浅色层次，但无法形成教程中的珠光反射。可跳过提亮，完成哑光版本。"
      : i === 1
        ? "先抖掉余粉，少量叠加，避免覆盖底色。"
        : "可沿用教程操作。",
  missingCapability: i === 2 ? ["珠光质地", "高反光能力"] : [],
  hardConstraints: [],
}));
