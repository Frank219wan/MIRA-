import { sampleProducts } from "../mocks/products";
import type { BeautyKitDTO } from "./api/dto";
import type { Product } from "../types/product";

const STORAGE_KEY = "mira-added-catalog-products";
const catalogById = new Map(sampleProducts.map((product) => [product.id, product]));

export const getCatalogProducts = () => sampleProducts.map((product) => structuredClone(product));

export function getCatalogProduct(productId: string) {
  const product = catalogById.get(productId);
  return product ? structuredClone(product) : undefined;
}

export function getAddedCatalogProductIds() {
  if (typeof localStorage === "undefined") return [];
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(value)) return [];
    return [...new Set(value.filter((id): id is string => typeof id === "string" && catalogById.has(id)))];
  } catch {
    return [];
  }
}

export function getAddedCatalogProducts() {
  return getAddedCatalogProductIds()
    .map((id) => getCatalogProduct(id))
    .filter((product): product is Product => Boolean(product));
}

export function addCatalogProduct(productId: string) {
  if (!catalogById.has(productId)) throw new Error("Unknown catalog product");
  const ids = [...new Set([...getAddedCatalogProductIds(), productId])];
  if (typeof localStorage !== "undefined") localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  return getAddedCatalogProducts();
}

export function mergeUserProducts(products: Product[]) {
  const merged = new Map(products.map((product) => [product.id, product]));
  for (const product of getAddedCatalogProducts()) merged.set(product.id, product);
  return [...merged.values()];
}

export function mergeAddedProductsIntoBeautyKit(dto: BeautyKitDTO): BeautyKitDTO {
  const products = new Map(dto.products.map((product) => [product.product_id, product]));
  for (const product of getAddedCatalogProducts()) {
    products.set(product.id, {
      product_id: product.id,
      name: product.productName,
      // Catalog display metadata is not verified capability evidence. The
      // matching engine keeps these products unscored until a catalog adapter
      // supplies reviewed color, finish, depth, texture and function data.
      capability_ids: ["capability-unverified"],
    });
  }
  return { ...dto, products: [...products.values()] };
}

export function productMatchesQuery(product: Product, query: string) {
  const search = query.trim().toLocaleLowerCase();
  if (!search) return true;
  return [
    product.productName,
    product.brand,
    product.category,
    ...product.shades.flatMap((shade) => [shade.shadeName, shade.hue, shade.finish]),
  ].some((value) => value.toLocaleLowerCase().includes(search));
}
