import { matches } from "../mocks/matching";
import { demo, withFallback } from "./base";
import { request } from "./api/client";
import { getRecipeDTO, getTutorial, isExampleTutorial } from "./tutorial";
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
      const adapted = adaptMatching(dto, recipe, adaptBeautyKit(beauty_kit));
      if (!isExampleTutorial()) return adapted;
      // The authored example is deliberately rendered from the local five-step
      // preset. Its canonical order mirrors the backend demo recipe, so align
      // identities here to let verified product matches reach the preset UI.
      const preset = await getTutorial();
      return adapted.map((match, index) => ({
        ...match,
        actionId: preset[index]?.id ?? match.actionId,
      }));
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
            score: null,
            capabilityChecks: [],
            reason: "尚无匹配结果",
            difference: "尚无匹配结果",
            impact: "尚未评估",
            missingCapability: [],
            hardConstraints: [],
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
