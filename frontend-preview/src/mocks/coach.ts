import type { CoachIntent } from "../types/guidance";
export const coachResponses: Record<CoachIntent, string> = {
  下一步: "这一部分完成了，我们继续下一步。",
  重复一下: "少量蘸取，轻轻落笔，再把边缘晕开。",
  这里对吗:
    "演示模式暂不判断实际位置。请对照目标区域，先用干净刷子比划范围，再少量上色。",
  我画重了怎么办:
    "先停止叠加，用干净的晕染刷轻扫边缘；必要时用少量打底色柔化。",
  我没有这支刷子: "可以换一支大小接近的干净软毛刷；用量减半，少量多次。",
};
export const coachIntents = Object.keys(coachResponses) as CoachIntent[];
