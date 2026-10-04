import type {
  StandardRecipeDTO,
  EngineActionDTO,
  PersonalizationResultDTO,
} from "../api/dto";
import type { PersonalizedAction } from "../../types/guidance";

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
        ? `眼线方向 ${p.direction_angle_deg.toFixed(2)}°；延伸系数 ${p.extension_factor.toFixed(3)}`
        : `下眼睑范围系数 ${p.range_factor.toFixed(3)}；强度系数 ${p.intensity_factor.toFixed(3)}`;
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
