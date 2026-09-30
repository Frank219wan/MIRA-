import { actions } from "./tutorial";
import { products } from "./products";
import type { MatchResult } from "../types/matching";
export const matches: MatchResult[] = actions.map((a, i) => ({
  actionId: a.id,
  status: i === 3 ? "missing" : i === 2 ? "partial" : "matched",
  bestMatch: products[0],
  score: i === 3 ? 32 : i === 2 ? 78 : 94,
  capabilityChecks: [
    { label: i === 3 ? "香槟色" : "所需色系", passed: true },
    { label: i === 3 ? "珠光质地" : "哑光质地", passed: i !== 3 },
    { label: i === 3 ? "高反光能力" : "易于晕染", passed: i !== 3 },
  ],
  difference:
    i === 3
      ? "颜色相近，但质地功能不同"
      : i === 2
        ? "暖棕色略深，用量需要减少"
        : "颜色与质地符合本步骤需求",
  impact:
    i === 3
      ? "可以保留浅色层次，但无法形成教程中的珠光反射。可跳过提亮，完成哑光版本。"
      : i === 2
        ? "先抖掉余粉，少量叠加，避免覆盖底色。"
        : "可沿用教程操作。",
  missingCapability: i === 3 ? ["珠光质地", "高反光能力"] : [],
}));
