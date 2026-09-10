import { getCompletedSteps } from "./coach";
import { getMatchResult } from "./matching";
import { hasFaceProfile } from "./face";
import { getPersonalizedTutorial } from "./personalizedTutorial";
export const getFinishSummary = async () => {
  const matches = await getMatchResult();
  const actions = await getPersonalizedTutorial();
  const adapted = hasFaceProfile();
  return {
    completed: getCompletedSteps().length,
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
    productChange: "产品替换 Reference Shade → " + actions[1].product,
  };
};
