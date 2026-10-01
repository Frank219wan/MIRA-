import type { MakeupAction } from "../../types/tutorial";
import type { PersonalizedAction } from "../../types/guidance";
import { personalizedTutorial } from "../../mocks/personalizedTutorial";
import type { MyTutorialResponseDTO } from "../api/dto";

export function adaptMyTutorialResponse(
  dto: MyTutorialResponseDTO,
): PersonalizedAction[] {
  if (dto.schema_version !== "0.2" || !Array.isArray(dto.steps))
    throw new Error("Invalid My Tutorial response");
  return dto.steps.map((step) => {
    if (step.standard_action.step_index !== step.step_index)
      throw new Error("Mismatched My Tutorial step");
    const match = step.match_result;
    return {
      actionId: `${dto.recipe_id}:${step.step_index}`,
      reference: {
        where: step.standard_action.area,
        direction: step.standard_action.motion,
        product: step.standard_action.product_requirement,
      },
      personalized: { where: step.where, direction: step.how },
      product:
        match?.best_match?.product_name ??
        match?.best_match?.name ??
        step.standard_action.product_requirement,
      goal: step.standard_action.goal,
      whyChanged: step.why,
      instructions: step.how,
      stopWhen: step.stop_when,
      personalizationStatus: step.personalization_status,
      matchDecision: match?.decision ?? undefined,
    };
  });
}
export function adaptPersonalizedTutorial(
  actions: MakeupAction[],
  consent: boolean,
): PersonalizedAction[] {
  const mock = personalizedTutorial(consent);
  return actions.map((a) => {
    const existing = mock.find((m) => m.actionId === a.id);
    if (existing) return structuredClone(existing);
    // New recipe actions retain standard directions until an actual adaptation contract exists.
    return {
      actionId: a.id,
      reference: {
        where: a.area,
        direction: a.motion,
        product: a.productRequirement,
      },
      personalized: { where: a.area, direction: a.motion },
      product: a.productRequirement,
      goal: a.goal,
      whyChanged: "个性化演示占位：当前保留原教程动作，尚未生成真实面部适配。",
      instructions: a.motion,
      stopWhen: a.targetResult,
      arGuidance: {
        polygon: [],
        standardRegion: { center: [50, 50], radius: [0, 0] },
        region: a.area,
        directionVector: [0, 0],
        intensity: a.intensity,
      },
    };
  });
}
