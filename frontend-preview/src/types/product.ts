export interface Shade {
  shadeName: string;
  hex: string;
  hue: string;
  depth: string;
  finish: string;
  pigmentation: string;
  blendability: string;
  reflectivity: string;
  texture: string;
}
export interface Product {
  id: string;
  brand: string;
  productName: string;
  category: "眼部" | "面部" | "唇部" | "眉部";
  productImage: string | null;
  shades: Shade[];
}
