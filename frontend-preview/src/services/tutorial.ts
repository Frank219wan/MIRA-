import { clearLocalAppearancePreferences } from "./localAppearance";
import { actions, stages } from "../mocks/tutorial";
import { demo, withFallback } from "./base";
import { request, ApiError } from "./api/client";
import { adaptRecipe } from "./adapters/tutorial";
import { apiConfig } from "../lib/config";
import type { StandardRecipeDTO, TutorialMediaInputDTO } from "./api/dto";
import type { TutorialInput } from "../types/tutorial";
import { clearProductUseMode } from "./productMode";
let pending: Promise<StandardRecipeDTO> | undefined;
let revision = 0;
let mediaInput: TutorialMediaInputDTO | undefined;
function parseInput(): TutorialMediaInputDTO {
  if (mediaInput) return mediaInput;
  const input: TutorialInput = JSON.parse(
    sessionStorage.getItem("mira-input") ||
      '{"kind":"example","name":"柔棕日常眼妆"}',
  );
  if (input.kind !== "example" || !apiConfig.exampleMediaPath)
    throw new Error("当前后端仅支持服务器媒体路径；上传文件和链接暂用参考方案");
  return {
    media_path: apiConfig.exampleMediaPath,
    media_kind: apiConfig.exampleMediaKind,
    recipe_id: `recipe-${crypto.randomUUID()}`,
    title: input.name,
  };
}
// Transport DTO is retained for matching/CV. Never reconstruct it from UI actions.
export function getRecipeDTO(): Promise<StandardRecipeDTO> {
  if (!pending) {
    const generation = revision;
    const id = sessionStorage.getItem("mira-recipe-id");
    pending = Promise.resolve()
      .then(async () => {
        if (id) {
          try {
            return await request<StandardRecipeDTO>(
              `/recipes/${encodeURIComponent(id)}`,
            );
          } catch (error) {
            if (!(error instanceof ApiError) || error.status !== 404)
              throw error;
            if (generation !== revision) throw error;
            sessionStorage.removeItem("mira-recipe-id");
          }
        }
        return request<StandardRecipeDTO>("/tutorials/parse", parseInput());
      })
      .then((dto) => {
        adaptRecipe(dto);
        if (generation === revision)
          sessionStorage.setItem("mira-recipe-id", dto.recipe_id);
        return dto;
      })
      .catch((e) => {
        if (generation === revision) pending = undefined;
        throw e;
      });
  }
  return pending;
}
export const getTutorial = () =>
  withFallback(
    "getTutorial",
    async () => adaptRecipe(await getRecipeDTO()),
    () => demo(actions),
  );
export const getParsingStages = () => demo(stages); // Visual sequence only, never backend progress.
export async function getRecipe(id: string) {
  return withFallback(
    "getRecipe",
    async () =>
      adaptRecipe(
        await request<StandardRecipeDTO>(`/recipes/${encodeURIComponent(id)}`),
      ),
    () => demo(actions),
  );
}
export const saveTutorialInput = async (input: TutorialInput) => {
  revision++;
  pending = undefined;
  mediaInput = undefined;
  sessionStorage.removeItem("mira-recipe-id");
  sessionStorage.removeItem("mira-completed");
  clearProductUseMode();
  clearLocalAppearancePreferences();
  sessionStorage.setItem("mira-input", JSON.stringify(input));
  return input;
};
// Integration entry point for a future uploader that returns a server-side path.
export async function parseTutorial(input: TutorialMediaInputDTO) {
  await saveTutorialInput({
    kind: input.media_kind === "video" ? "video" : "image",
    name: input.title,
  });
  mediaInput = input;
  return getTutorial();
}

// Stable diagnostic identity survives production minification.
Object.assign(getTutorial, { statusKey: "getTutorial" });
