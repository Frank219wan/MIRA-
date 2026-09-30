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
  const [actions, face, adaptation] = await Promise.all([
    getTutorial(),
    getFaceProfileContext(),
    getCVAdaptation(),
  ]);
  // Replace only the action adapter when backend adds actual per-step adaptation.
  return {
    actions: adaptPersonalizedTutorial(actions, hasFaceProfile()),
    face,
    adaptation,
    provenance: {
      actions: "mock/standard-fallback",
      geometry: face.provenance.geometry,
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
      faceAdapted: false,
      actions: context.actions,
      provenance: context.provenance,
    }),
  );
  return true;
};
