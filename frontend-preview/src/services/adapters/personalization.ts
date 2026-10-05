import type {
  StandardRecipeDTO,
  EngineActionDTO,
  PersonalizationResultDTO,
} from "../api/dto";
import type { PersonalizedAction } from "../../types/guidance";

// Presentation only: compare engine values without inventing physical distances.
export function describeAdjustment(
  parameter: string,
  before: number,
  after: number,
): string {
  const choices: Record<string, [string, string, string]> = {
    direction_angle_deg: [
      "眼线方向保持不变",
      "眼尾向上扬一些",
      "眼线方向放平一些",
    ],
    extension_factor: [
      "眼尾延伸长度保持不变",
      "眼尾延伸画长一些",
      "眼尾延伸画短一些",
    ],
    range_factor: [
      "下眼睑晕染范围保持不变",
      "下眼睑晕染范围扩大一些",
      "下眼睑晕染范围收窄一些",
    ],
    intensity_factor: [
      "下眼睑上色深浅保持不变",
      "下眼睑上色加深一些",
      "下眼睑上色减淡一些",
    ],
  };
  return (
    choices[parameter]?.[
      Math.abs(after - before) < 1e-8 ? 0 : after > before ? 1 : 2
    ] || "根据面部信息调整"
  );
}

// Parser action_units contain no numeric parameters. These are the documented
// Engine v0 demo baselines, NOT measured tutorial values or inferred rules.
const baseline = {
  A04: { direction_angle_deg: 10, extension_factor: 1 },
  A02: { range_factor: 1, intensity_factor: 1 },
};
export function toEngineRecipe(recipe: StandardRecipeDTO) {
  const mapped: { tutorialActionId: string; action: EngineActionDTO }[] = [];
  for (const unit of recipe.action_units) {
    const area = unit.area.toLowerCase();
    const product = unit.product_requirement.toLowerCase();
    const id =
      /^(upper lash line|upper eyelid|上睫毛根部|上眼睑)$/.test(area) &&
      /eyeliner|眼线/.test(product)
        ? "A04"
        : /^(lower eyelid|lower lid|下眼睑)$/.test(area) &&
            /shadow|眼影/.test(product)
          ? "A02"
          : null;
    if (id)
      mapped.push({
        tutorialActionId: `${recipe.recipe_id}:${unit.step_index}`,
        action: { action_id: id, parameters: { ...baseline[id] } },
      });
  }
  return {
    standardRecipe: {
      recipe_id: recipe.recipe_id,
      actions: mapped.map((x) => x.action),
    },
    tutorialActionIds: mapped.map((x) => x.tutorialActionId),
    parameterSource: "frontend-demo-baseline" as const,
    targetEffectSource: "engine-v0-cat-eye-only" as const,
  };
}
export function applyPersonalization(
  actions: PersonalizedAction[],
  mapping: ReturnType<typeof toEngineRecipe>,
  result: PersonalizationResultDTO,
): PersonalizedAction[] {
  if (
    result.recipe_id !== mapping.standardRecipe.recipe_id ||
    result.target_effect !== "cat_eye" ||
    !Array.isArray(result.personalized_actions) ||
    result.personalized_actions.length !== mapping.tutorialActionIds.length
  )
    throw new Error("Invalid personalization recipe response");
  const updates = new Map<string, PersonalizedAction>();
  result.personalized_actions.forEach((item, index) => {
    const expected = mapping.standardRecipe.actions[index];
    const action = actions.find(
      (a) => a.actionId === mapping.tutorialActionIds[index],
    );
    if (
      !action ||
      item.action_id !== expected.action_id ||
      !item.original_parameters ||
      !item.personalized_parameters ||
      !Array.isArray(item.applied_rules) ||
      !item.applied_rules.every((x) => typeof x === "string") ||
      !Array.isArray(item.adjustments) ||
      !item.adjustments.length
    )
      throw new Error("Invalid personalization action response");
    for (const [key, value] of Object.entries(expected.parameters)) {
      if (
        item.original_parameters[key] !== value ||
        !Number.isFinite(item.personalized_parameters[key])
      )
        throw new Error("Invalid personalization parameters");
    }
    for (const adj of item.adjustments) {
      if (
        !Array.isArray(adj.rule_ids) ||
        !adj.rule_ids.every((x) => item.applied_rules.includes(x)) ||
        typeof adj.feature_path !== "string" ||
        typeof adj.operation !== "string" ||
        ![
          adj.feature_value,
          adj.adjustment_value,
          adj.original_value,
          adj.personalized_value,
        ].every(Number.isFinite) ||
        adj.original_value !== item.original_parameters[adj.parameter] ||
        adj.personalized_value !== item.personalized_parameters[adj.parameter]
      )
        throw new Error("Invalid personalization adjustments");
    }
    const p = item.personalized_parameters;
    const summary =
      item.action_id === "A04"
        ? `眼线方向 ${p.direction_angle_deg.toFixed(2)}°；${describeAdjustment("extension_factor", item.original_parameters.extension_factor, p.extension_factor)}`
        : `${describeAdjustment("range_factor", item.original_parameters.range_factor, p.range_factor)}；${describeAdjustment("intensity_factor", item.original_parameters.intensity_factor, p.intensity_factor)}`;
    updates.set(action.actionId, {
      ...action,
      personalized: { ...action.personalized, direction: summary },
      instructions: `${action.instructions}。${summary}。`,
      whyChanged: `根据面部参数应用 ${item.applied_rules.join("、")}；基于猫眼预设参数调整。`,
      personalizationSource: "backend-personalization",
      backendPersonalization: structuredClone(item),
      parameterSource: mapping.parameterSource,
    });
  });
  return actions.map((a) => updates.get(a.actionId) ?? a);
}
