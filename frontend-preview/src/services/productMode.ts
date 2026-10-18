import type { MakeupAction } from "../types/tutorial";

export type ProductUseMode = "beauty-kit" | "generic";
export type TutorialProduct = {
  actionId: string;
  label: string;
  source: "matched" | "generic";
};

const STORAGE_KEY = "mira-product-mode";

export function hasProductUseMode() {
  const value = sessionStorage.getItem(STORAGE_KEY);
  return value === "beauty-kit" || value === "generic";
}

export function getProductUseMode(): ProductUseMode {
  return sessionStorage.getItem(STORAGE_KEY) === "beauty-kit"
    ? "beauty-kit"
    : "generic";
}

export function setProductUseMode(mode: ProductUseMode) {
  sessionStorage.setItem(STORAGE_KEY, mode);
}

export function clearProductUseMode() {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function resolveGenericProduct(
  action: MakeupAction,
): Omit<TutorialProduct, "actionId"> {
  const text = `${action.name} ${action.goal} ${action.productRequirement}`;
  let label = action.productRequirement;

  if (/黑色眼线/.test(text) && /睫毛膏|睫毛/.test(text))
    label = "黑色眼线笔与黑色睫毛膏";
  else if (/粉紫细闪/.test(text) && /眼线/.test(text))
    label = "粉紫细闪眼影与黑色眼线笔";
  else if (/深紫灰/.test(text)) label = "冷调紫灰眼影中的深色 / 加深色";
  else if (/浅紫灰/.test(text)) label = "浅紫灰哑光眼影 / 打底色";
  else if (/冷棕/.test(text)) label = "冷棕色哑光眼影 / 卧蚕阴影";
  else if (/深棕/.test(text) || (/眼影/.test(text) && /深色|加深/.test(text)))
    label = "大地色眼影盘中的深棕色 / 加深色";
  else if (/暖棕/.test(text)) label = "大地色眼影盘中的暖棕色 / 过渡色";
  else if (/眼影/.test(text) && /过渡|衔接/.test(text))
    label = "大地色眼影盘中的中棕色 / 过渡色";
  else if (/浅米|米白|打底/.test(text)) label = "浅色哑光眼影 / 打底色";
  else if (/香槟|珠光|提亮|高反光/.test(text)) label = "浅色珠光眼影 / 提亮色";
  else if (/棕色/.test(text)) label = "大地色眼影盘中的棕色 / 阴影色";

  return { label, source: "generic" };
}

export function genericProducts(actions: MakeupAction[]): TutorialProduct[] {
  return actions.map((action) => ({
    actionId: action.id,
    ...resolveGenericProduct(action),
  }));
}
