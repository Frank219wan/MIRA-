import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X, Camera, Search, Plus } from "lucide-react";
import { Button } from "../ui/button";
import { Placeholder } from "../ui/primitives";
export function AddProduct() {
  const [mode, setMode] = useState("");
  const [file, setFile] = useState("");
  return (
    <Dialog.Root
      onOpenChange={() => {
        setMode("");
        setFile("");
      }}
    >
      <Dialog.Trigger asChild>
        <Button variant="outline">
          <Plus size={15} />
          添加产品
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-backdrop" />
        <Dialog.Content className="modal">
          <Dialog.Title>把熟悉的产品，放进工具库</Dialog.Title>
          <Dialog.Description>
            产品录入功能准备中，可先查看入口与流程。
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
                aria-label="搜索品牌或产品"
                placeholder="搜索品牌或产品"
                disabled
              />
              <p>产品库搜索将在后续开放。</p>
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
