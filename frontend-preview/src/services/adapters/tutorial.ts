import { chineseText, chineseActionName } from "./chinese";
import type { StandardRecipeDTO } from "../api/dto";
import type { MakeupAction } from "../../types/tutorial";
export function adaptRecipe(dto: StandardRecipeDTO): MakeupAction[] {
  if (
    dto.schema_version !== "1.0" ||
    !dto.recipe_id ||
    !Array.isArray(dto.action_units) ||
    !dto.action_units.length
  )
    throw new Error("Invalid recipe response");
  return dto.action_units.map((a, i) => {
    if (
      a.step_index !== i + 1 ||
      ![
        a.area,
        a.goal,
        a.product_requirement,
        a.tool,
        a.motion,
        a.intensity,
        a.target_result,
      ].every((x) => typeof x === "string" && x.trim())
    )
      throw new Error("Invalid action unit");
    const [startTime, endTime] = a.time_range_seconds ?? [0, 0]; // 0 = unavailable, not inferred video timing.
    if (
      ![startTime, endTime].every(Number.isFinite) ||
      startTime < 0 ||
      endTime < startTime
    )
      throw new Error("Invalid action time range");
    return {
      id: `${dto.recipe_id}:${a.step_index}`,
      order: a.step_index,
      name: chineseActionName(a.goal, a.area),
      area: chineseText(a.area),
      goal: chineseText(a.goal),
      productRequirement: chineseText(a.product_requirement),
      tool: chineseText(a.tool),
      motion: chineseText(a.motion),
      intensity: chineseText(a.intensity),
      targetResult: chineseText(a.target_result),
      startTime,
      endTime,
    };
  });
}
