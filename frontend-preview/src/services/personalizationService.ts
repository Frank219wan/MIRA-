import { withFallback } from "./base";
import { getFaceProfileDTO } from "./face";
import { getRecipeDTO, isExampleTutorial } from "./tutorial";
import { request, ApiError } from "./api/client";
import { adaptFaceProfile } from "./adapters/face";
import {
  toEngineRecipe,
  applyPersonalization,
} from "./adapters/personalization";
import { mockFaceProfileV03 } from "../mocks/faceProfileV03";
import type { PersonalizedAction } from "../types/guidance";
import type {
  PersonalizationRequestDTO,
  PersonalizationResultDTO,
} from "./api/dto";

// Base URL, timeout and structured HTTP errors are owned by the shared API client.
export async function personalizeTutorialActions(
  actions: PersonalizedAction[],
) {
  if (isExampleTutorial()) return actions; // The preset steps have no measured recipe to personalize.
  const measured = getFaceProfileDTO();
  const face = measured ?? structuredClone(mockFaceProfileV03);
  const faceSource = measured ? "scan" : "mock";
  return withFallback(
    "getPersonalization",
    async () => {
      adaptFaceProfile(face);
      const recipe = await getRecipeDTO();
      const mapping = toEngineRecipe(recipe);
      if (!mapping.standardRecipe.actions.length) return actions;
      // Do not merge responses into a fallback or different tutorial.
      if (
        !mapping.tutorialActionIds.every((id) =>
          actions.some((a) => a.actionId === id),
        )
      )
        throw new Error("Personalization tutorial identity mismatch");
      const payload: PersonalizationRequestDTO = {
        face_profile: face,
        standard_recipe: mapping.standardRecipe,
        target_effect: "cat_eye",
      };
      let result: PersonalizationResultDTO;
      try {
        result = await request<PersonalizationResultDTO>(
          "/personalization",
          payload,
        );
      } catch (error) {
        if (import.meta.env?.DEV)
          console.warn(
            "[MIRA personalization] POST /personalization failed",
            error instanceof ApiError
              ? {
                  status: error.status,
                  code: error.code,
                  requestId: error.requestId,
                  message: error.message,
                }
              : error,
          );
        throw error;
      }
      if (JSON.stringify(getFaceProfileDTO()) !== JSON.stringify(measured))
        return actions;
      return applyPersonalization(actions, mapping, result).map((action) =>
        action.personalizationSource === "backend-personalization"
          ? { ...action, faceProfileSource: faceSource as "scan" | "mock" }
          : action,
      );
    },
    () => actions,
  );
}
