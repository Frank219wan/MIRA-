import { getCompletedSteps } from "./coach";
import { getMatchResult } from "./matching";
import { getPersonalizedTutorial } from "./personalizedTutorial";
import { getProductUseMode } from "./productMode";
export const getFinishSummary = async () => {
  const productMode = getProductUseMode();
  const matches = productMode === "beauty-kit" ? await getMatchResult() : [];
  const actions = await getPersonalizedTutorial();
  const adapted = false; // CV currently validates geometry only; no measured action adjustments.
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
    adjustmentCount: adapted ? 2 : 0,
    adapted,
    changes: adapted ? ["外眼角范围 33% → 25%", "晕染方向 0° → +15°"] : [],
    productChange:
      productMode === "generic"
        ? "本次使用通用产品描述，例如：" +
          (actions[1]?.product ?? actions[0]?.product ?? "按步骤能力选择")
        : "产品替换 参考色号 → " +
          (actions[1]?.product ?? actions[0]?.product ?? "未提供"),
  };
};
