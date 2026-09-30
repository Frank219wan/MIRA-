import { products, categories } from "../mocks/products";
import { demo, withFallback } from "./base";
import { request } from "./api/client";
import { adaptBeautyKit } from "./adapters/beautyKit";
import type { BeautyKitDTO } from "./api/dto";
export async function getBeautyKitDTO() {
  const dto = await request<BeautyKitDTO>("/beauty-kit");
  adaptBeautyKit(dto);
  return dto;
}
export const getBeautyKit = () =>
  withFallback(
    "getBeautyKit",
    async () => adaptBeautyKit(await getBeautyKitDTO()),
    () => demo(products),
  );
export const getProductCategories = () => demo(categories);

// Stable diagnostic identity survives production minification.
Object.assign(getBeautyKit, { statusKey: "getBeautyKit" });
