import type { MakeupAction } from "../types/tutorial";
export const regions = [
  "额头",
  "左脸颊",
  "右脸颊",
  "鼻部",
  "下巴",
  "眼周",
] as const;
export type LocalRegion = (typeof regions)[number];
export type AppearancePreference = "keep" | "soften" | "cover" | "integrate";
export interface LocalAppearancePreference {
  region: LocalRegion;
  preference: AppearancePreference;
  integrateStyle: "natural" | "highlight" | null;
}
export interface LocalAppearanceGuidance extends LocalAppearancePreference {
  source: "frontend-preference";
  label: string;
  instruction: string;
  stopWhen: string;
  actionIds: string[];
}
export const preferenceOptions = [
  ["keep", "保留原有呈现", "保持这个区域现在的状态，只调整周围妆容。"],
  ["soften", "柔和修饰", "轻微均匀周围色差或边界，同时保留原有特征。"],
  ["cover", "增强遮盖", "通过少量分层，提高局部底妆的覆盖度。"],
  [
    "integrate",
    "融入妆容",
    "把这个区域纳入当前 Look，让周围妆容与它自然结合。",
  ],
] as const;
const KEY = "mira-local-appearance";
export function isLocalPreference(v: unknown): v is LocalAppearancePreference {
  const p = v as LocalAppearancePreference;
  return (
    !!p &&
    regions.includes(p.region) &&
    preferenceOptions.some((o) => o[0] === p.preference) &&
    (p.preference === "integrate"
      ? ["natural", "highlight"].includes(p.integrateStyle || "")
      : p.integrateStyle === null)
  );
}
export function getLocalAppearancePreferences(): LocalAppearancePreference[] {
  try {
    const data: unknown = JSON.parse(sessionStorage.getItem(KEY) || "[]");
    return Array.isArray(data)
      ? data
          .filter(isLocalPreference)
          .filter((p, i, a) => a.findIndex((x) => x.region === p.region) === i)
      : [];
  } catch {
    return [];
  }
}
export function setLocalAppearancePreferences(
  values: LocalAppearancePreference[],
) {
  if (!values.every(isLocalPreference))
    throw new Error("请选择完整的区域与呈现方式。");
  sessionStorage.setItem(KEY, JSON.stringify(values));
}
export function clearLocalAppearancePreferences() {
  sessionStorage.removeItem(KEY);
}
// Authored guidance, separate from backend parameters; never introduces engine actions.
export function compileLocalAppearance(
  preferences: LocalAppearancePreference[],
  actions: MakeupAction[],
): LocalAppearanceGuidance[] {
  return preferences.map((p) => {
    const text = {
      keep: [
        "底妆经过该区域时减少覆盖，从周围轻轻向边缘过渡。",
        "保持原有呈现，周围衔接自然即可。",
      ],
      soften: [
        "少量轻拍边界，逐次观察过渡，保留原有肤色与纹理特征。",
        "过渡达到你希望的柔和程度即可。",
      ],
      cover: [
        "局部底妆少量分层按压，每层完成后观察覆盖效果，再决定是否继续叠加。",
        "达到你满意的覆盖程度即可。",
      ],
      integrate:
        p.integrateStyle === "highlight"
          ? [
              "先保留该区域，再参考本次教程已有的色彩或光泽，少量调整周围妆容，逐次观察整体搭配。",
              "达到你希望的呈现程度即可，无需额外叠加。",
            ]
          : [
              "保持原有视觉特征，在周围轻柔衔接本次教程的色彩，避免直接覆盖。",
              "原有特征与周围妆容自然衔接即可。",
            ],
    }[p.preference];
    const aliases: Record<LocalRegion, RegExp> = {
      额头: /额头|前额|forehead/i,
      左脸颊: /左脸颊|左颊|left cheek/i,
      右脸颊: /右脸颊|右颊|right cheek/i,
      鼻部: /鼻|nose/i,
      下巴: /下巴|chin/i,
      眼周: /眼|睑|eye|lid/i,
    };
    // Only attach to explicitly relevant complexion steps, never override eyeliner/eye-shadow geometry.
    const actionIds = actions
      .filter(
        (a) =>
          /底妆|粉底|遮瑕|foundation|concealer/i.test(
            a.productRequirement + a.name,
          ) &&
          (aliases[p.region].test(a.area) ||
            /全脸|面部整体|full face/i.test(a.area)),
      )
      .map((a) => a.id);
    return {
      ...p,
      source: "frontend-preference",
      label: preferenceOptions.find((o) => o[0] === p.preference)![1],
      instruction: text[0],
      stopWhen: text[1],
      actionIds,
    };
  });
}
