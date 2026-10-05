import type { PersonalizedAction } from "../types/guidance";
import { describeAdjustment } from "./adapters/personalization";
import { getCompletedSteps } from "./coach";
import { getMatchResult } from "./matching";
import { getPersonalizedTutorial } from "./personalizedTutorial";
import { getProductUseMode } from "./productMode";
export const getFinishSummary = async () => {
  const productMode = getProductUseMode();
  const matches = productMode === "beauty-kit" ? await getMatchResult() : [];
  const actions = await getPersonalizedTutorial();
  const adjustmentSummary = summarizeAdjustments(actions);
  return {
    completed: getCompletedSteps().length,
    productMode,
    reused: new Set(
      matches
        .filter((m) => m.status !== "missing")
        .map((m) => m.bestMatch?.id)
        .filter(Boolean),
    ).size,
    missing: matches.flatMap((m) => m.missingCapability),
    ...adjustmentSummary,
    productChange:
      productMode === "generic"
        ? "本次使用通用产品描述，例如：" +
          (actions[1]?.product ?? actions[0]?.product ?? "按步骤能力选择")
        : "产品替换 参考色号 → " +
          (actions[1]?.product ?? actions[0]?.product ?? "未提供"),
  };
};

export function summarizeAdjustments(actions: PersonalizedAction[]) {
  const changes: string[] = [];
  let exampleProfile = false;
  actions.forEach((action, index) => {
    if (
      action.personalizationSource !== "backend-personalization" ||
      !action.backendPersonalization
    )
      return;
    const result = action.backendPersonalization;
    for (const parameter of new Set(
      result.adjustments.map((item) => item.parameter),
    )) {
      const before = result.original_parameters[parameter],
        after = result.personalized_parameters[parameter];
      if (
        !Number.isFinite(before) ||
        !Number.isFinite(after) ||
        Math.abs(after - before) < 1e-8
      )
        continue;
      changes.push(
        `步骤 ${index + 1}：${describeAdjustment(parameter, before, after)}`,
      );
      if (action.faceProfileSource === "mock") exampleProfile = true;
    }
  });
  return {
    adjustmentCount: changes.length,
    adapted: changes.length > 0,
    changes,
    exampleProfile,
  };
}
