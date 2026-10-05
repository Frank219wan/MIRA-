import { withFallback } from "./base";
import {
  hasFaceProfile,
  getFaceProfileDTO,
  getFaceProfileContext,
} from "./face";
import { getTutorial, getRecipeDTO } from "./tutorial";
import { request } from "./api/client";
import { adaptFaceProfile } from "./adapters/face";
import { adaptPersonalizedTutorial } from "./adapters/personalizedTutorial";
import { getMatchResult } from "./matching";
import {
  genericProducts,
  getProductUseMode,
  type TutorialProduct,
} from "./productMode";
import { personalizeTutorialActions } from "./personalizationService";
export { personalizeTutorialActions } from "./personalizationService";
import type { CVAdaptationDTO } from "./api/dto";
export async function getCVAdaptation(): Promise<CVAdaptationDTO | null> {
  const face_profile = getFaceProfileDTO();
  if (!face_profile) return null; // Never submit a mock profile as a measured scan.
  return withFallback(
    "getCVAdaptation",
    async () => {
      const recipe = await getRecipeDTO();
      const result = await request<CVAdaptationDTO>("/cv-adaptation", {
        recipe,
        face_profile,
      });
      if (result.recipe_id !== recipe.recipe_id)
        throw new Error("Mismatched CV recipe");
      adaptFaceProfile(result.face_profile);
      return result;
    },
    () => null,
  );
}
export async function getPersonalizedTutorialContext() {
  const productMode = getProductUseMode();
  const [actions, face, adaptation] = await Promise.all([
    getTutorial(),
    getFaceProfileContext(),
    getCVAdaptation(),
  ]);
  const generic = genericProducts(actions);
  let products: TutorialProduct[] = generic;
  if (productMode === "beauty-kit") {
    const matches = await getMatchResult();
    products = generic.map((fallback) => {
      const match = matches.find((item) => item.actionId === fallback.actionId);
      return match?.status !== "missing" && match?.bestMatch
        ? {
            actionId: fallback.actionId,
            label: match.bestMatch.productName,
            source: "matched" as const,
          }
        : fallback;
    });
  }
  const personalized = await personalizeTutorialActions(
    adaptPersonalizedTutorial(actions, hasFaceProfile(), products),
  );
  const backendCount = personalized.filter(
    (a) => a.personalizationSource === "backend-personalization",
  ).length;
  return {
    actions: personalized,
    face,
    adaptation,
    productMode,
    provenance: {
      actions: backendCount
        ? "backend-personalization/partial"
        : "mock/standard-fallback",
      perAction: personalized.map((a) => ({
        actionId: a.actionId,
        source: a.personalizationSource,
      })),
      products: products.map((product) => product.source),
      geometry: face.provenance.geometry,
      personalizationFace:
        personalized.find((a) => a.faceProfileSource)?.faceProfileSource ??
        "unavailable",
      adaptation: adaptation ? "backend-passthrough" : "unavailable",
    } as const,
  };
}
export const getPersonalizedTutorial = async () =>
  (await getPersonalizedTutorialContext()).actions;
export const savePersonalizedTutorial = async () => {
  const context = await getPersonalizedTutorialContext();
  localStorage.setItem(
    "mira-saved-tutorial",
    JSON.stringify({
      savedAt: new Date().toISOString(),
      faceAdapted: context.actions.some(
        (a) =>
          a.personalizationSource === "backend-personalization" &&
          a.faceProfileSource === "scan",
      ),
      productMode: context.productMode,
      actions: context.actions,
      provenance: context.provenance,
    }),
  );
  return true;
};
