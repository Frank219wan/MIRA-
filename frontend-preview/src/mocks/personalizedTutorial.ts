import { actions } from "./tutorial";
import type { PersonalizedAction } from "../types/guidance";
export function personalizedTutorial(adapted: boolean): PersonalizedAction[] {
  return actions.map((a, i) => ({
    actionId: a.id,
    reference: {
      where: a.area,
      direction: i === 1 ? "水平向外 →" : a.motion,
      product: a.productRequirement,
    },
    personalized: {
      where: adapted && i === 1 ? "外侧约 25%" : a.area,
      direction: adapted && i === 1 ? "向外上方 ↗15°" : a.motion,
    },
    product: [
      "日常眼影盘 #01",
      "日常眼影盘 #04",
      "日常眼影盘 #03",
      "日常眼影盘 #02 · 哑光替代",
      "日常眼影盘 #04",
    ][i],
    goal: a.goal,
    whyChanged:
      i === 3
        ? "现有香槟色为哑光，保留浅色层次，无法还原珠光反射；也可跳过本步。"
        : adapted && i === 1
          ? "根据示例眼尾走势，缩小加深范围，并让晕染方向轻微上扬。"
          : i === 2
            ? "已有暖棕色略深，减少蘸粉量，让衔接更柔和。"
            : adapted
              ? "当前区域与示例面部档案适配，保留原教程动作。"
              : "尚未使用面部适配，保留参考教程的标准位置和方向。",
    instructions:
      i === 3
        ? "取少量哑光香槟色轻按中央，仅增加浅色层次，不追求珠光效果。"
        : adapted && i === 1
          ? "蘸取少量深棕色，落在外侧约四分之一，向外上方轻扫，再用干净刷子柔化边缘。"
          : a.motion,
    stopWhen:
      i === 3
        ? "中央形成柔和浅色层次即可。"
        : a.targetResult + "即可，不再继续叠加。",
    arGuidance: {
      polygon: adapted
        ? ([
            [
              [54, 40],
              [67, 39],
              [68, 44],
              [54, 45],
            ],
            [
              [61, 43],
              [75, 39],
              [70, 47],
              [62, 48],
            ],
            [
              [55, 38],
              [69, 38],
              [71, 43],
              [55, 42],
            ],
            [
              [58, 41],
              [63, 41],
              [64, 44],
              [58, 44],
            ],
            [
              [62, 46],
              [70, 45],
              [68, 49],
              [62, 48],
            ],
          ][i] as [number, number][])
        : [],
      standardRegion: {
        center: [
          [61, 43],
          [67, 44],
          [62, 40],
          [61, 43],
          [66, 47],
        ][i] as [number, number],
        radius: [
          [8, 4],
          [5, 3],
          [9, 3],
          [3, 2],
          [5, 2],
        ][i] as [number, number],
      },
      region: adapted && i === 1 ? "外眼角适配区域" : a.area,
      directionVector: adapted && i === 1 ? [0.97, -0.26] : [1, 0],
      intensity: a.intensity,
    },
  }));
}
