import type { MakeupAction } from "../types/tutorial";
import {
  compileLocalAppearance,
  type LocalAppearancePreference,
  type LocalAppearanceGuidance,
} from "./localAppearance";
import { request } from "./api/client";
import { withFallback } from "./base";

const preferenceMap = {
  keep: "KEEP",
  soften: "BLEND",
  cover: "COVER",
} as const;
export function toSpecialAreaProfile(preferences: LocalAppearancePreference[]) {
  return {
    schema_version: "0.1",
    image_sample_id: "current-tutorial-selection",
    areas: preferences.flatMap((p) => {
      // The engine has no equivalent for our two integrate styles. Keep their authored guidance.
      if (p.preference === "integrate" || !p.selection) return [];
      const { x, y, width, height } = p.selection;
      if (
        ![x, y, width, height].every(Number.isFinite) ||
        width <= 0 ||
        height <= 0
      )
        return [];
      return [
        {
          area_id: p.id || p.region,
          source: "user_selected",
          user_label: p.userLabel?.trim() || "",
          label_source: "user_provided",
          // Location is explicitly chosen by the user, never inferred from the image.
          location: ({ "左脸颊": "subject_left_cheek", "右脸颊": "subject_right_cheek", "额头": "forehead", "鼻部": "nose", "下巴": "chin", "上唇": "upper_lip", "眼周": "other", "局部区域": "other" } as const)[p.region],
          preference: preferenceMap[p.preference],
          polygon: Array.from({ length: 16 }, (_, i) => ({
            x_norm: Math.min(
              1,
              Math.max(0, x + (width / 2) * Math.cos((i * Math.PI) / 8)),
            ),
            y_norm: Math.min(
              1,
              Math.max(0, y + (height / 2) * Math.sin((i * Math.PI) / 8)),
            ),
          })),
        },
      ];
    }),
  };
}
export function normalizeSpecialAreaGuidance(
  value: unknown,
  profile: ReturnType<typeof toSpecialAreaProfile>,
  fallback: LocalAppearanceGuidance[],
): LocalAppearanceGuidance[] {
  const dto = value as {
    schema_version?: string;
    image_sample_id?: string;
    tutorial_type?: string;
    guidance_blocks?: {
      area_id: string;
      preference: string;
      decision_source: string;
      guidance_zh: string;
    }[];
  };
  if (
    !dto ||
    dto.schema_version !== "0.1" ||
    dto.image_sample_id !== profile.image_sample_id ||
    dto.tutorial_type !== "complexion_base_makeup" ||
    !Array.isArray(dto.guidance_blocks) ||
    dto.guidance_blocks.length !== profile.areas.length
  )
    throw new Error("Invalid special area response");
  const blocks = dto.guidance_blocks;
  if (
    new Set(blocks.map((b) => b?.area_id)).size !== blocks.length ||
    profile.areas.some(
      (a) =>
        !blocks.some(
          (b) =>
            b?.area_id === a.area_id &&
            b.preference === a.preference &&
            b.decision_source === "user_preference" &&
            typeof b.guidance_zh === "string" &&
            b.guidance_zh.trim(),
        ),
    )
  )
    throw new Error("Mismatched special area guidance");
  return fallback.map((g) => {
    const block = blocks.find((b) => b.area_id === (g.id || g.region));
    return block
      ? { ...g, instruction: block.guidance_zh, source: "backend-special-area" }
      : g;
  });
}
export async function getLocalAppearanceGuidance(
  preferences: LocalAppearancePreference[],
  actions: MakeupAction[],
) {
  const fallback = compileLocalAppearance(preferences, actions);
  const profile = toSpecialAreaProfile(preferences);
  if (!profile.areas.length) return fallback;
  return withFallback(
    "getLocalAppearanceGuidance",
    async () =>
      normalizeSpecialAreaGuidance(
        await request("/special-area-guidance", { profile }),
        profile,
        fallback,
      ),
    () => fallback,
  );
}
