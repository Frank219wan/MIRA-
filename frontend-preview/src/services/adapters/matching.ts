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
      score: typeof item?.score === "number" && Number.isFinite(item.score) ? item.score : null,
      capabilityChecks: (item?.capability_checks ?? []).map((check) => ({
        label: `${check.label} · 权重 ${check.weight}%`,
        passed: check.matched,
      })),
      reason: item?.reason || "尚无匹配原因",
      difference: item?.difference || (item?.note
        ? `${chineseText(item.note, "匹配说明待补充中文")}`
        : "尚无差异分析"),
      impact: item?.impact || "尚无妆效评估",
      missingCapability: item?.missing_capabilities ?? [],
      hardConstraints: item?.hard_constraints ?? [],
      provenance: {
        status: item ? "backend" : "frontend-fallback",
        score: item?.verification_status === "verified" && typeof item.score === "number" && Number.isFinite(item.score)
          ? "backend"
          : "frontend-fallback",
        details: item ? "backend" : "frontend-fallback",
      },
    };
  });
}
