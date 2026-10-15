import type { Product } from "../types/product";
export const products: Product[] = [
  {
    id: "palette-a",
    brand: "演示资料",
    productName: "日常眼影盘 · 日常大地色盘",
    category: "眼部",
    productImage: null,
    shades: [
      ["#01 米白", "#e4cdb2", "米色", "浅"],
      ["#02 香槟", "#d1b68b", "香槟色", "浅"],
      ["#03 暖棕", "#a97551", "暖棕色", "中"],
      ["#04 深棕", "#604333", "深棕色", "深"],
    ].map((a) => ({
      shadeName: a[0],
      hex: a[1],
      hue: a[2],
      depth: a[3],
      finish: "哑光",
      pigmentation: "中",
      blendability: "高",
      reflectivity: "低",
      texture: "粉质",
    })),
  },
];
export const categories = ["眼部", "面部", "唇部", "眉部"] as const;

// Display-only hackathon examples. These are never returned by getBeautyKit or sent to matching.
// Brand-series names below are verified from L'Oréal Paris US product pages; colour chips are illustrative.
const exampleShade = (shadeName: string, hex: string, finish: string) => ({
  shadeName,
  hex,
  hue: shadeName,
  depth: "示例",
  finish,
  pigmentation: "示例",
  blendability: "示例",
  reflectivity: "示例",
  texture: "示例",
});
export const sampleProducts: Product[] = [
  {
    id: "display-week2-concept-palette",
    brand: "Week 2 · 案例概念色",
    productName: "A01–A05 眼妆替代组合",
    category: "眼部",
    productImage: null,
    shades: [
      exampleShade("S01 米白", "#e9dfd2", "提亮示意"),
      exampleShade("S06 浅豆沙", "#b99ba4", "阴影示意"),
      exampleShade("S15 深灰紫", "#584757", "哑光示意"),
      exampleShade("S20 黑色", "#2d292e", "哑光示意"),
      exampleShade("S25 粉色细闪", "#d8a9bc", "细闪示意"),
    ],
  },
  {
    id: "display-panorama-mascara",
    brand: "L'Oréal Paris · 品类参考",
    productName: "Voluminous Panorama 睫毛膏",
    category: "眼部",
    productImage: null,
    shades: [exampleShade("黑色示意", "#332b2b", "睫毛产品")],
  },
  {
    id: "display-eye-primer",
    brand: "陈列示例",
    productName: "轻薄眼部打底膏",
    category: "眼部",
    productImage: null,
    shades: [exampleShade("自然米", "#d9c3ac", "柔雾")],
  },
  {
    id: "display-eye-liner",
    brand: "L'Oréal Paris · 品类参考",
    productName: "Infallible Grip 机械凝胶眼线笔",
    category: "眼部",
    productImage: null,
    shades: [exampleShade("Brown Denim", "#694b3f", "色彩示意"), exampleShade("Intense Black", "#342b29", "色彩示意")],
  },
  {
    id: "display-shadow-matte",
    brand: "L'Oréal Paris · 品类参考",
    productName: "Paradise Le Shadow Stick · 420 Brown Bliss",
    category: "眼部",
    productImage: null,
    shades: [exampleShade("420 Brown Bliss", "#795441", "色彩示意")],
  },
  {
    id: "display-shadow-shimmer",
    brand: "L'Oréal Paris · 品类参考",
    productName: "Paradise Le Shadow Stick · Nude Lights",
    category: "眼部",
    productImage: null,
    shades: [exampleShade("Nude Lights", "#d2ad8f", "色彩示意")],
  },
  {
    id: "display-base-cushion",
    brand: "陈列示例",
    productName: "轻透气垫底妆",
    category: "面部",
    productImage: null,
    shades: [exampleShade("自然米", "#d9b99b", "自然光泽"), exampleShade("暖杏色", "#c99f7c", "自然光泽")],
  },
  {
    id: "display-lip-colour",
    brand: "陈列示例",
    productName: "日常唇釉",
    category: "唇部",
    productImage: null,
    shades: [exampleShade("玫瑰豆沙", "#a66d70", "水润"), exampleShade("暖赤茶", "#9f5c4e", "水润")],
  },
  {
    id: "display-brow-pencil",
    brand: "陈列示例",
    productName: "细芯眉笔",
    category: "眉部",
    productImage: null,
    shades: [exampleShade("灰棕", "#77685c", "自然"), exampleShade("深棕", "#51413a", "自然")],
  },
];
