import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X, Camera, Search, Plus } from "lucide-react";
import { Button } from "../ui/button";
import { Placeholder } from "../ui/primitives";
import {
  addCatalogProduct,
  getAddedCatalogProductIds,
  getCatalogProducts,
  productMatchesQuery,
} from "../../services/productLibrary";

export function AddProduct({ onProductAdded }: { onProductAdded?: () => void }) {
  const [mode, setMode] = useState("搜索产品库");
  const [file, setFile] = useState("");
  const [query, setQuery] = useState("");
  const [addedIds, setAddedIds] = useState(getAddedCatalogProductIds);
  const catalogProducts = getCatalogProducts().filter((product) => productMatchesQuery(product, query));
  function add(productId: string) {
    const products = addCatalogProduct(productId);
    setAddedIds(products.map((product) => product.id));
    onProductAdded?.();
  }
  return (
    <Dialog.Root
      onOpenChange={() => {
        setMode("搜索产品库");
        setFile("");
        setQuery("");
      }}
    >
      <Dialog.Trigger asChild>
        <Button variant="outline">
          <Search size={15} />
          搜索产品库
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-backdrop" />
        <Dialog.Content className="modal">
          <Dialog.Title>搜索产品库</Dialog.Title>
          <Dialog.Description>
            浏览当前系统已有目录，并将需要的产品加入 My Beauty Kit。当前未连接欧莱雅官方产品数据库。
          </Dialog.Description>
          <Dialog.Close className="modal-close" aria-label="关闭">
            <X size={18} />
          </Dialog.Close>
          <div className="modal-tabs">
            {[
              ["拍摄我的化妆包", Camera],
              ["搜索产品库", Search],
              ["手动添加", Plus],
            ].map(([label, Icon]) => (
              <Button
                variant="outline"
                key={String(label)}
                onClick={() => setMode(String(label))}
              >
                {typeof Icon !== "string" && <Icon size={16} />} {String(label)}
              </Button>
            ))}
          </div>
          {mode === "拍摄我的化妆包" ? (
            <>
              <label className="upload">
                上传 / 拍摄平铺图
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={(e) => setFile(e.target.files?.[0]?.name || "")}
                />
                {file && <small>已选择：{file}，当前不上传或识别。</small>}
              </label>
              <Placeholder label="识别结果候选列表" />
              <p>后续可逐项确认或修改识别结果，再加入工具库。</p>
              <Button disabled>确认并加入工具库 · 即将开放</Button>
            </>
          ) : mode === "搜索产品库" ? (
            <>
              <input
                type="search"
                aria-label="搜索产品库中的品牌、类型、名称或色号"
                placeholder="品牌、类型、名称或色号"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <p className="catalog-disclaimer">当前结果来自项目内置演示目录，不代表官方合作、实时库存或市场在售状态。</p>
              <div className="catalog-results" aria-live="polite">
                {catalogProducts.map((product) => {
                  const added = addedIds.includes(product.id);
                  return (
                    <article className="catalog-result" key={product.id}>
                      {product.productImage ? <img src={product.productImage} alt="" /> : null}
                      <div>
                        <small>{product.brand} · {product.category}</small>
                        <h3>{product.productName}</h3>
                        <p>{product.shades.map((shade) => shade.shadeName).join(" · ")}</p>
                      </div>
                      <Button variant="outline" disabled={added} onClick={() => add(product.id)}>
                        {added ? "已在我的产品库" : "加入 My Beauty Kit"}
                      </Button>
                    </article>
                  );
                })}
                {!catalogProducts.length && (
                  <div className="catalog-empty">
                    <strong>没有找到相关产品</strong>
                    <p>试试品牌、产品类型、名称或其他色号关键词。</p>
                  </div>
                )}
              </div>
            </>
          ) : mode === "手动添加" ? (
            <>
              <input aria-label="品牌" placeholder="品牌" disabled />
              <input aria-label="产品名称" placeholder="产品名称" disabled />
              <Button disabled>保存产品 · 即将开放</Button>
            </>
          ) : (
            <p>选择一种方式，了解产品录入流程。</p>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
