import { withFallback } from "./base";
import {
  hasFaceProfile,
  getFaceProfileDTO,
  getFaceProfileContext,
} from "./face";
import { getTutorial, getRecipeDTO } from "./tutorial";
import { getBeautyKitDTO } from "./products";
import { request } from "./api/client";
import { adaptFaceProfile } from "./adapters/face";
import {
  adaptMyTutorialResponse,
  adaptPersonalizedTutorial,
} from "./adapters/personalizedTutorial";
import type {
  CVAdaptationDTO,
  MyTutorialRequestDTO,
  MyTutorialResponseDTO,
} from "./api/dto";
import type { PersonalizedAction } from "../types/guidance";

type PersonalizedTutorialContext = {
  actions: PersonalizedAction[];
  face: Awaited<ReturnType<typeof getFaceProfileContext>>;
  adaptation: CVAdaptationDTO | null;
  provenance: { actions: string; geometry: string; adaptation: string };
};
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
  return withFallback<PersonalizedTutorialContext>(
    "getPersonalizedTutorial",
    async () => {
      const face_profile = getFaceProfileDTO();
      if (!face_profile) throw new Error("No measured Face Profile is available");
      const [recipe, beauty_kit, face] = await Promise.all([
        getRecipeDTO(),
        getBeautyKitDTO(),
        getFaceProfileContext(),
      ]);
      const payload: MyTutorialRequestDTO = {
        recipe,
        beauty_kit,
        face_profile,
        face_profile_id: "frontend-session-face-profile",
        target_effect: "cat_eye",
      };
      const tutorial = await request<MyTutorialResponseDTO>(
        "/tutorials/my-tutorial",
        payload,
      );
      if (tutorial.recipe_id !== recipe.recipe_id)
        throw new Error("Mismatched My Tutorial recipe");
      return {
        actions: adaptMyTutorialResponse(tutorial),
        face,
        adaptation: null,
        provenance: {
          actions: "backend-my-tutorial-v0.2",
          geometry: face.provenance.geometry,
          adaptation: "backend-orchestration",
        } as const,
      };
    },
    async () => {
      const [actions, face, adaptation] = await Promise.all([
        getTutorial(),
        getFaceProfileContext(),
        getCVAdaptation(),
      ]);
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
    },
  );
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
