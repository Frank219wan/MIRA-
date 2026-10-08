import { useNavigate } from "react-router-dom";
import { copyPreferencePreview } from "../../services/preferencePreview";
import { useState, useRef, useEffect, type PointerEvent } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "../ui/button";
import {
  getLocalAppearancePreferences,
  setLocalAppearancePreferences,
  type AppearancePreference,
  type SelectionRegion,
} from "../../services/localAppearance";
const choices = [
  ["keep", "保留原有呈现", "保持这个区域现在的状态，只调整周围妆容。"],
  ["soften", "柔和修饰", "轻微调整周围色差与边界，同时保留原有特征。"],
  ["cover", "增强遮盖", "提高局部覆盖度，让整体肤色更均匀。"],
  ["integrate", "融入妆容", "让这个区域参与当前 Look 的色彩与妆容设计。"],
] as const;
export function LocalAppearanceCard({
  image,
  editor = false,
}: {
  image?: string;
  editor?: boolean;
}) {
  const nav = useNavigate();
  const [editingId, setEditingId] = useState<string>();
  const sectionRef = useRef<HTMLElement>(null);
  const [saved, setSaved] = useState(getLocalAppearancePreferences);
  const [selecting, setSelecting] = useState(editor && saved.length === 0);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (selecting) sectionRef.current?.scrollIntoView({ block: "start" });
  }, [selecting]);
  const [region, setRegion] = useState<SelectionRegion>();
  const [preference, setPreference] = useState<AppearancePreference>();
  const [style, setStyle] = useState<"natural" | "highlight" | null>(null);
  const [error, setError] = useState("");
  function begin(id?: string) {
    const existing = saved.find((p) => (p.id || p.region) === id);
    setEditingId(id);
    setError("");
    setRegion(existing?.selection);
    setPreference(existing?.preference);
    setStyle(existing?.integrateStyle ?? null);
    setSelecting(true);
  }
  async function enter() {
    await copyPreferencePreview(image);
    nav("/face-preferences");
  }
  function remove(id: string) {
    try {
      const next = saved.filter((p) => (p.id || p.region) !== id);
      setLocalAppearancePreferences(next);
      setSaved(next);
    } catch {
      setError("未能保存，请重试。");
    }
  }
  function cancel() {
    setOpen(false);
    setSelecting(false);
    setError("");
  }
  function place(e: PointerEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    setRegion({
      x: Math.min(0.9, Math.max(0.1, (e.clientX - r.left) / r.width)),
      y: Math.min(0.92, Math.max(0.08, (e.clientY - r.top) / r.height)),
      width: 0.2,
      height: 0.16,
    });
  }
  function finish() {
    if (!region || !preference || (preference === "integrate" && !style))
      return;
    try {
      const next = {
        id: editingId || crypto.randomUUID(),
        region: "局部区域" as const,
        selection: region,
        preference,
        integrateStyle: preference === "integrate" ? style : null,
      };
      const updated = [
        ...saved.filter((p) => (p.id || p.region) !== editingId),
        next,
      ];
      setLocalAppearancePreferences(updated);
      setSaved(updated);
      cancel();
    } catch {
      setError("未能保存，请重试。");
    }
  }
  return (
    <section
      ref={sectionRef}
      className="local-appearance-card"
      id="local-appearance"
      aria-label="局部呈现偏好"
    >
      {selecting ? (
        <>
          <h2>选择想单独设置的区域</h2>
          <p>在面部轻点一个位置，后续教程会根据你的选择调整。</p>
          <div
            className="region-canvas"
            role="button"
            tabIndex={0}
            aria-label="选择面部位置，点击或按方向键调整选区"
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId);
              place(e);
            }}
            onPointerMove={(e) => {
              if (e.currentTarget.hasPointerCapture(e.pointerId)) place(e);
            }}
            onKeyDown={(e) => {
              if (
                [
                  "ArrowLeft",
                  "ArrowRight",
                  "ArrowUp",
                  "ArrowDown",
                  "Enter",
                  " ",
                ].includes(e.key)
              ) {
                e.preventDefault();
                setRegion((r) => ({
                  x: Math.min(
                    0.9,
                    Math.max(
                      0.1,
                      (r?.x ?? 0.5) +
                        (e.key === "ArrowRight"
                          ? 0.03
                          : e.key === "ArrowLeft"
                            ? -0.03
                            : 0),
                    ),
                  ),
                  y: Math.min(
                    0.92,
                    Math.max(
                      0.08,
                      (r?.y ?? 0.5) +
                        (e.key === "ArrowDown"
                          ? 0.03
                          : e.key === "ArrowUp"
                            ? -0.03
                            : 0),
                    ),
                  ),
                  width: 0.2,
                  height: 0.16,
                }));
              }
            }}
          >
            <img
              src={image || "/assets/face/scan-guide.png"}
              alt={image ? "本次面部画面" : "扫脸示意图"}
              draggable={false}
            />
            {saved
              .filter((p) => p.selection && (p.id || p.region) !== editingId)
              .map((p, i) => (
                <span
                  key={p.id || p.region}
                  className="local-selection saved-selection"
                  style={{
                    left: `${p.selection!.x * 100}%`,
                    top: `${p.selection!.y * 100}%`,
                    width: `${p.selection!.width * 100}%`,
                    height: `${p.selection!.height * 100}%`,
                  }}
                >
                  {i + 1}
                </span>
              ))}
            {region && (
              <span
                className="local-selection"
                style={{
                  left: `${region.x * 100}%`,
                  top: `${region.y * 100}%`,
                  width: `${region.width * 100}%`,
                  height: `${region.height * 100}%`,
                }}
              />
            )}
          </div>
          {!image && <small>在扫脸示意图上标记位置。</small>}
          <div className="local-actions">
            <Button variant="tertiary" onClick={cancel}>
              取消
            </Button>
            <Button variant="outline" onClick={() => setRegion(undefined)}>
              重新选择
            </Button>
            <Button disabled={!region} onClick={() => setOpen(true)}>
              确认这个区域
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className="local-card-heading">
            <h2>局部呈现偏好</h2>
            <small>
              {saved.length ? `✓ 已设置 ${saved.length} 个区域` : "可选"}
            </small>
          </div>
          {saved.map((item, i) => (
            <div className="local-region-row" key={item.id || item.region}>
              <p>
                区域 {i + 1} ·{" "}
                {choices.find((c) => c[0] === item.preference)?.[1]}
                {item.integrateStyle &&
                  ` · ${item.integrateStyle === "natural" ? "自然保留" : "突出呈现"}`}
              </p>
              {editor && (
                <div className="local-actions">
                  <Button
                    variant="tertiary"
                    onClick={() => begin(item.id || item.region)}
                  >
                    调整区域 {i + 1}
                  </Button>
                  <Button
                    variant="tertiary"
                    onClick={() => remove(item.id || item.region)}
                  >
                    删除区域 {i + 1}
                  </Button>
                </div>
              )}
            </div>
          ))}
          {!saved.length && (
            <p>如果有某个区域希望采用不同的上妆方式，可以单独告诉 MIRA。</p>
          )}
          <Button
            variant="tertiary"
            onClick={() => (editor ? begin() : void enter())}
          >
            {editor
              ? saved.length
                ? "添加另一个区域"
                : "标记一个区域"
              : saved.length
                ? "调整"
                : "标记一个区域"}
          </Button>
          {error && <p role="alert">{error}</p>}
        </>
      )}
      <Dialog.Root
        open={open}
        onOpenChange={(value) => {
          if (!value) cancel();
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="modal-backdrop" />
          <Dialog.Content className="modal local-preference-sheet">
            <div className="local-preference-body">
              <Dialog.Title>这里想怎么呈现？</Dialog.Title>
              <Dialog.Description>
                选择今天更符合你想法的方式，之后也可以随时修改。
              </Dialog.Description>
              <fieldset className="preference-options">
                <legend className="sr-only">呈现方式</legend>
                {choices.map(([id, title, description]) => (
                  <label key={id}>
                    <input
                      type="radio"
                      name="local-preference"
                      checked={preference === id}
                      onChange={() => {
                        setPreference(id);
                        setStyle(null);
                      }}
                    />
                    <span>
                      <strong>{title}</strong>
                      <small>{description}</small>
                    </span>
                  </label>
                ))}
              </fieldset>
              {preference === "integrate" && (
                <fieldset className="preference-options">
                  <legend>希望怎样融入？</legend>
                  {(
                    [
                      [
                        "natural",
                        "自然保留",
                        "保持原有视觉特征，让周围妆容自然衔接。",
                      ],
                      [
                        "highlight",
                        "突出呈现",
                        "通过色彩、光泽或位置设计，让这个区域成为 Look 的一部分。",
                      ],
                    ] as const
                  ).map(([id, title, description]) => (
                    <label key={id}>
                      <input
                        type="radio"
                        name="local-integrate"
                        checked={style === id}
                        onChange={() => setStyle(id)}
                      />
                      <span>
                        <strong>{title}</strong>
                        <small>{description}</small>
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}
              {error && <p role="alert">{error}</p>}
            </div>
            <div className="local-actions">
              <Button
                variant="tertiary"
                onClick={() => {
                  setOpen(false);
                  setSelecting(true);
                }}
              >
                返回选区
              </Button>
              <Button
                disabled={!preference || (preference === "integrate" && !style)}
                onClick={finish}
              >
                确认偏好
              </Button>
              <Button variant="tertiary" onClick={cancel}>
                今天不设置
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
