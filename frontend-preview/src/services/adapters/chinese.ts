// Presentation translations only. Original DTOs stay unchanged for API requests.
const terms: Record<string, string> = {
  "upper eyelid": "整个上眼睑",
  crease: "眼窝褶皱处",
  "outer corner": "外眼角",
  "center lid": "上眼睑中央",
  "upper lash line": "上睫毛根部",
  prime: "均匀眼睑底色",
  "add depth": "增加眼窝层次",
  define: "勾勒轮廓",
  brighten: "提亮眼睑",
  "eye primer": "眼部打底产品",
  "matte transition shadow": "哑光过渡色眼影",
  "matte deep shadow": "哑光深色眼影",
  "shimmer shadow": "珠光眼影",
  eyeliner: "眼线产品",
  fingertip: "指腹",
  "blending brush": "晕染刷",
  "detail brush": "细节刷",
  "flat shader brush": "平头眼影刷",
  "liner brush": "眼线刷",
  pat: "少量轻拍，均匀按压",
  "windshield-wiper blend": "沿眼窝来回轻扫，柔和晕染",
  "press and blend": "轻按上色，再晕开边缘",
  "short stroke": "沿睫毛根部以短笔触描画",
  light: "轻柔",
  sheer: "轻薄",
  medium: "适中",
  strong: "较强",
  "even base": "底色自然均匀",
  "soft transition": "深浅色柔和过渡",
  "defined outer corner": "眼尾轮廓清晰、边界自然",
  "reflective lid": "眼睑中央呈现柔亮光泽",
  "clean lash-line definition": "睫毛根部线条干净清晰",
  "neutral palette": "大地色眼影盘",
  "week 1 structural placeholder; no matching algorithm executed.":
    "当前为接口占位结果，尚未执行产品匹配算法。",
};
export function chineseText(text: string, fallback = "中文说明待补充"): string {
  const translated = terms[text.trim().toLowerCase()];
  if (translated) return translated;
  // Existing Chinese remains verbatim; never invent a translation for unseen model output.
  return /[a-z]/i.test(text) ? fallback : text;
}
export function chineseActionName(goal: string, area: string): string {
  const names: Record<string, string> = {
    "prime|upper eyelid": "眼皮打底",
    "add depth|crease": "眼窝过渡",
    "define|outer corner": "加深眼尾",
    "brighten|center lid": "中央提亮",
    "define|upper lash line": "描画眼线",
  };
  return (
    names[`${goal.toLowerCase()}|${area.toLowerCase()}`] ??
    `${chineseText(goal, "完成本步妆容")} · ${chineseText(area, "指定区域")}`
  );
}
