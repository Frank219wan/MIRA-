import { chineseText } from "./chinese";
import type { BeautyKitDTO } from "../api/dto";
import type { Product } from "../../types/product";
import { products } from "../../mocks/products";
// Explicit demo metadata mapping. Never associate unknown products by array position.
const localMetadata: Record<string, Product> = {
  "product-neutral-palette": products[0],
  "palette-a": products[0],
};
export const productMetadataSource = (id: string) =>
  localMetadata[id] ? "local-demo-metadata" : "frontend-placeholder";
export function adaptBeautyKit(dto: BeautyKitDTO): Product[] {
  if (!dto.kit_id || !Array.isArray(dto.products))
    throw new Error("Invalid beauty kit");
  return dto.products.map((p) => {
    if (!p.product_id || !p.name || !Array.isArray(p.capability_ids))
      throw new Error("Invalid beauty kit product");
    const metadata = localMetadata[p.product_id];
    return {
      id: p.product_id,
      productName: chineseText(p.name, "产品名称待补充中文"),
      brand: metadata?.brand ?? "品牌待补充",
      category: metadata?.category ?? "眼部",
      productImage: metadata?.productImage ?? null,
      shades: structuredClone(metadata?.shades ?? []),
    };
  });
}
