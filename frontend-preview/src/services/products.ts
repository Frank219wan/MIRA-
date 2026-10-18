import { products, categories } from "../mocks/products";
import { demo, withFallback } from "./base";
import { request } from "./api/client";
import { adaptBeautyKit } from "./adapters/beautyKit";
import { mergeAddedProductsIntoBeautyKit, mergeUserProducts } from "./productLibrary";
import type { BeautyKitDTO } from "./api/dto";
export async function getBeautyKitDTO() {
  const dto = await request<BeautyKitDTO>("/beauty-kit");
  adaptBeautyKit(dto);
  return mergeAddedProductsIntoBeautyKit(dto);
}
export const getBeautyKit = () =>
  withFallback(
    "getBeautyKit",
    async () => adaptBeautyKit(await getBeautyKitDTO()),
    () => demo(mergeUserProducts(products)),
  );
export const getProductCategories = () => demo(categories);

// Stable diagnostic identity survives production minification.
Object.assign(getBeautyKit, { statusKey: "getBeautyKit" });
