import type { MakeupAction } from "../../types/tutorial";
import type { PersonalizedAction } from "../../types/guidance";
import { personalizedTutorial } from "../../mocks/personalizedTutorial";
import type { TutorialProduct } from "../productMode";
export function adaptPersonalizedTutorial(
  actions: MakeupAction[],
  consent: boolean,
  products: TutorialProduct[] = [],
): PersonalizedAction[] {
  const mock = personalizedTutorial(consent);
  return actions.map((a) => {
    const existing = mock.find((m) => m.actionId === a.id);
    const product = products.find((item) => item.actionId === a.id) ?? {
      actionId: a.id,
      label: a.productRequirement,
      source: "generic" as const,
    };
    if (existing)
      return {
        ...structuredClone(existing),
        personalizationSource: "mock/standard-fallback",
        product: product.label,
        productSource: product.source,
      };
    // New recipe actions retain standard directions until an actual adaptation contract exists.
    return {
      actionId: a.id,
      personalizationSource: "mock/standard-fallback",
      reference: {
        where: a.area,
        direction: a.motion,
        product: a.productRequirement,
      },
      personalized: { where: a.area, direction: a.motion },
      product: product.label,
      productSource: product.source,
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
