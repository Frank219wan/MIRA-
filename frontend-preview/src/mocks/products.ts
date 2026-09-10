import type { Product } from "../types/product";
export const products: Product[] = [
  {
    id: "palette-a",
    brand: "我的收藏",
    productName: "Palette A · 日常大地色盘",
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
