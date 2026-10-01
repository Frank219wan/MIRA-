import { chineseText } from "./chinese";
import type { MatchingResultDTO, StandardRecipeDTO } from "../api/dto";
import type { MatchResult } from "../../types/matching";
import type { Product } from "../../types/product";
import { adaptRecipe } from "./tutorial";
export type AdaptedMatch = MatchResult & {
  provenance: {
    status: "backend" | "frontend-fallback";
    score: "backend" | "frontend-fallback";
    details: "backend" | "frontend-fallback";
  };
};
export function adaptMatching(
  dto: MatchingResultDTO,
  recipe: StandardRecipeDTO,
  products: Product[],
): AdaptedMatch[] {
  if (dto.recipe_id !== recipe.recipe_id || !Array.isArray(dto.items))
    throw new Error("Mismatched recipe in matching response");
  const statuses = {
    matched: "matched",
    unmatched: "missing",
    substitution_candidate: "partial",
  } as const;
  const seen = new Set<number>();
  for (const item of dto.items) {
    if (
      !Object.hasOwn(statuses, item.status) ||
      !Number.isInteger(item.step_index) ||
      item.step_index < 1 ||
      item.step_index > recipe.action_units.length ||
      seen.has(item.step_index)
    )
      throw new Error("Invalid matching item");
    seen.add(item.step_index);
  }
  return adaptRecipe(recipe).map((a) => {
    const item = dto.items.find((x) => x.step_index === a.order);
    return {
      actionId: a.id,
      status: item ? statuses[item.status] : "missing",
      bestMatch: products.find((p) => p.id === item?.product_id) ?? null,
      score: item?.match_score ?? 0,
      capabilityChecks: item
        ? [
            ...item.satisfied_capabilities.map((label) => ({ label, passed: true })),
            ...item.missing_capabilities.map((label) => ({ label, passed: false })),
          ]
        : [],
      difference: item?.difference
        ? chineseText(item.difference, "匹配差异待补充中文")
        : "后端暂未提供差异分析（前端占位）",
      impact: item?.impact
        ? chineseText(item.impact, "妆效影响待补充中文")
        : "后端暂未评估妆效影响（前端占位）",
      missingCapability: item?.missing_capabilities ?? [],
      reason: item?.reason ?? undefined,
      functionalConflict: item?.functional_conflict,
      provenance: {
        status: item ? "backend" : "frontend-fallback",
        score: item ? "backend" : "frontend-fallback",
        details: item ? "backend" : "frontend-fallback",
      },
    };
  });
}
