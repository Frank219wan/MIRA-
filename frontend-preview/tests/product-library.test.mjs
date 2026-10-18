import test from "node:test";
import assert from "node:assert/strict";
import {
  addCatalogProduct,
  getAddedCatalogProductIds,
  getCatalogProducts,
  mergeAddedProductsIntoBeautyKit,
  mergeUserProducts,
  productMatchesQuery,
} from "../src/services/productLibrary.ts";

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

test("catalog search covers brand, type, name and shade", () => {
  const catalog = getCatalogProducts();
  const primer = catalog.find((product) => product.id === "display-eye-primer");
  assert.ok(primer);
  assert.equal(productMatchesQuery(primer, "NYX"), true);
  assert.equal(productMatchesQuery(primer, "眼部"), true);
  assert.equal(productMatchesQuery(primer, "primer"), true);
  assert.equal(productMatchesQuery(primer, "自然米"), true);
  assert.equal(productMatchesQuery(primer, "不存在的色号"), false);
});

test("adding a catalog product persists it in My Beauty Kit and matching DTO", () => {
  globalThis.localStorage = storage();
  addCatalogProduct("display-eye-primer");
  addCatalogProduct("display-eye-primer");
  assert.deepEqual(getAddedCatalogProductIds(), ["display-eye-primer"]);
  const products = mergeUserProducts([]);
  assert.equal(products[0].productName.includes("Primer"), true);
  const dto = mergeAddedProductsIntoBeautyKit({
    schema_version: "1.0",
    kit_id: "kit-test",
    name: "Test kit",
    products: [],
  });
  assert.deepEqual(dto.products, [{
    product_id: "display-eye-primer",
    name: products[0].productName,
    capability_ids: ["capability-unverified"],
  }]);
});

test("unknown catalog ids are rejected and broken storage is ignored", () => {
  globalThis.localStorage = storage();
  localStorage.setItem("mira-added-catalog-products", "broken");
  assert.deepEqual(getAddedCatalogProductIds(), []);
  assert.throws(() => addCatalogProduct("not-in-catalog"));
});
