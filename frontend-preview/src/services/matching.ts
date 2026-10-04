import { matches } from "../mocks/matching";
import { demo, withFallback } from "./base";
import { request } from "./api/client";
import { getRecipeDTO, getTutorial } from "./tutorial";
import { getBeautyKitDTO } from "./products";
import { adaptBeautyKit } from "./adapters/beautyKit";
import { adaptMatching } from "./adapters/matching";
import type { MatchingResultDTO } from "./api/dto";
import type { MatchResult } from "../types/matching";
export type ServiceMatch = MatchResult & {
  provenance: { status: string; score: string; details: string };
};
export const getMatchResult = (): Promise<ServiceMatch[]> =>
  withFallback(
    "getMatchResult",
    async () => {
      const [recipe, beauty_kit] = await Promise.all([
        getRecipeDTO(),
        getBeautyKitDTO(),
      ]);
      const dto = await request<MatchingResultDTO>("/matching", {
        recipe,
        beauty_kit,
      });
      if (dto.beauty_kit_id !== beauty_kit.kit_id)
        throw new Error("Mismatched beauty kit");
      return adaptMatching(dto, recipe, adaptBeautyKit(beauty_kit));
    },
    async () => {
      const actions = await getTutorial();
      const mock = await demo(matches);
      return actions.map((a) => {
        const existing = mock.find((m) => m.actionId === a.id);
        // Do not attach unrelated demo products to a newly parsed action by index.
        return {
          ...(existing ?? {
            actionId: a.id,
            status: "missing" as const,
            bestMatch: null,
            score: 0,
            capabilityChecks: [],
            difference: "演示占位：尚无匹配结果",
            impact: "尚未评估",
            missingCapability: [],
          }),
          provenance: {
            status: "mock",
            score: existing ? "mock" : "frontend-fallback",
            details: "mock",
          },
        };
      });
    },
  );

// Stable diagnostic identity survives production minification.
Object.assign(getMatchResult, { statusKey: "getMatchResult" });
