import type { MakeupAction } from "../../types/tutorial";

export type GuideKind = "base" | "outer" | "highlight" | "lower" | "liner" | "blend" | "neutral";

export const guideNotes: Record<GuideKind, string> = {
  base: "从睫毛根部薄铺至眼窝，向上、向外柔化边缘。",
  outer: "深色集中在外眼角约 1/3 与外 V，向外上方逐渐晕淡。",
  highlight: "珠光集中轻按在眼皮中央，边缘与哑光底色自然衔接。",
  lower: "贴近下睫毛根部，由外向内轻扫，保持范围细窄。",
  liner: "从内侧沿上睫毛根部描画，内细外略粗，再顺势延伸眼尾。",
  blend: "用干净晕染刷沿深浅交界小幅打圈，直到边界自然。",
  neutral: "请结合步骤文字与镜中妆效确认范围。",
};

export function guideKindFor(action?: MakeupAction): GuideKind {
  const text = `${action?.name} ${action?.area} ${action?.goal} ${action?.productRequirement}`;
  return /眼线|睫毛根部/.test(text) && !/下眼|下睫毛/.test(text) ? "liner"
    : /下眼|下睫毛/.test(text) ? "lower"
      : /提亮|珠光|中央/.test(text) ? "highlight"
        : /衔接|过渡|晕染/.test(action?.name || "") ? "blend"
          : /眼尾|加深|outer corner/i.test(text) ? "outer"
            : /打底|上眼睑|眼皮|prime/i.test(text) ? "base" : "neutral";
}
