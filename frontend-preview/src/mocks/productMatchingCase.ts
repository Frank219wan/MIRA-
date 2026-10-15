// Week 2 product-substitution case. Display only: never sent to matching APIs.
export type CaseStep = {
  id: string;
  name: string;
  requirement: string;
  reference: string;
  source: string;
  kit: string;
  status: "Best Match" | "Match" | "Low Match → Alternative" | "Conditional Match / Alternative";
  difference: string;
  guidance: string;
  impact: "Low" | "Medium" | "High";
  swatches: string[];
};

const shadowSource = "https://www.lorealparisusa.com/makeup/eye/eye-shadow/paradise-le-shadow-stick";
export const matchingCase: CaseStep[] = [
  {
    id: "A01",
    name: "上眼皮打底",
    requirement: "浅灰粉 · 浅 · 哑光；适合大面积建立基础色",
    reference: "欧莱雅巴黎 Paradise Le Shadow Stick 眼影品类参考；浅灰粉哑光为概念色",
    source: shadowSource,
    kit: "色调接近但偏深的眼影 + S01 米白（概念色）",
    status: "Low Match → Alternative",
    difference: "色调接近，但主色偏深；直接大面积使用会让底色比目标更深。眼影棒仅作近似品类参考，不等同案例中的粉状眼影。",
    guidance: "减少偏深眼影的取粉量，先薄铺；再少量使用 S01 辅助调浅。S01 不单独承担整片眼皮打底。",
    impact: "Medium",
    swatches: ["#a98894", "#e9dfd2"],
  },
  {
    id: "A02",
    name: "下眼睑 / 卧蚕",
    requirement: "中浅粉紫或灰粉阴影色 + 浅色局部提亮",
    reference: "欧莱雅巴黎 Paradise Le Shadow Stick 眼影品类参考；浅豆沙与米白为概念色",
    source: shadowSource,
    kit: "S06 浅豆沙 + S01 米白（概念色）",
    status: "Match",
    difference: "核心颜色分工基本满足；局部提亮色不能代替阴影色。",
    guidance: "S06 塑造下眼睑阴影和层次；S01 只用于局部与卧蚕提亮。",
    impact: "Low",
    swatches: ["#b99ba4", "#e9dfd2"],
  },
  {
    id: "A03",
    name: "眼尾加深",
    requirement: "深灰紫 · 深冷调 · 哑光；要有足够深度塑造眼尾轮廓",
    reference: "欧莱雅巴黎 Paradise Le Shadow Stick 眼影品类参考；深灰紫为概念色",
    source: shadowSource,
    kit: "S15 深灰紫（概念色）",
    status: "Best Match",
    difference: "案例设定中没有关键能力缺失；具体质地仍须以手边实物确认。",
    guidance: "直接用 S15 加深眼尾，不需要寻找替代品。",
    impact: "High",
    swatches: ["#584757"],
  },
  {
    id: "A04",
    name: "小猫眼眼线",
    requirement: "黑色或极深色；形成细而清晰的小猫眼线条",
    reference: "欧莱雅巴黎 Infallible Grip Mechanical Gel Eyeliner · Intense Black（眼线产品参考）",
    source: "https://www.lorealparisusa.com/makeup/eye/eyeliner/grip-mechanical-gel-makeup-eyeliner",
    kit: "S20 黑色哑光眼影（概念色）+ 极细刀锋刷",
    status: "Conditional Match / Alternative",
    difference: "黑影的颜色和深度接近，但眼影不等于眼线产品；线条清晰度、稳定性和操作难度不同。",
    guidance: "优先使用专门眼线产品；只有黑影时，须配足够细的刀锋刷，少量分段勾勒，并提示晕染和失手风险。",
    impact: "High",
    swatches: ["#2d292e"],
  },
  {
    id: "A05",
    name: "睫毛 + 提亮",
    requirement: "睫毛产品 + 浅色珠光或细闪，用于睫毛和局部提亮",
    reference: "欧莱雅巴黎 Voluminous Panorama 睫毛膏 + Paradise Le Shadow Stick 眼影品类参考；粉色细闪为概念色",
    source: "https://www.lorealparisusa.com/makeup/eye/mascara/panorama-mascara-washable",
    kit: "睫毛产品 + S25 粉色细闪（概念色）",
    status: "Match",
    difference: "核心品类基本满足；示例未验证具体睫毛膏或细闪的实物表现。",
    guidance: "睫毛产品负责睫毛效果；S25 只在目标区域局部提亮。",
    impact: "Medium",
    swatches: ["#3a3030", "#d8a9bc"],
  },
];

export const eyelinerDirectCase: Pick<CaseStep, "kit" | "status" | "difference" | "guidance"> = {
  kit: "专门黑色眼线产品",
  status: "Best Match",
  difference: "案例设定中，产品形态和线条要求直接对应。",
  guidance: "优先使用专门眼线产品，沿眼尾分段画出细线。",
};
