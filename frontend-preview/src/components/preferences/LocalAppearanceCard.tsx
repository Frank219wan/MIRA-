import { useNavigate } from "react-router-dom";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent,
} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "../ui/button";
import { getStaticFace } from "../../services/staticFace";
import { copyPreferencePreview } from "../../services/preferencePreview";
import { publicAsset } from "../../lib/assets";
import {
  getLocalAppearancePreferences,
  setLocalAppearancePreferences,
  type AppearancePreference,
  type LocalRegion,
  regions,
  isPhotoSelectionCurrent,
} from "../../services/localAppearance";
import {
  convexHull,
  displayPointToRaw,
  ellipsePolygon,
  isSimplePolygon,
  pointInPolygon,
  polygonArea,
  rawPointToDisplay,
  selectionBounds,
  type MediaGeometry,
  type NormalizedPoint,
} from "../../services/selectionGeometry";

const choices = [
  ["keep", "KEEP · 保留", "保持原本颜色与纹理，只在周围轻柔衔接。"],
  ["soften", "BLEND · 柔和融合", "轻微调整周围色差与边界，同时保留原有特征。"],
  ["cover", "COVER · 增强遮盖", "少量分层提高局部覆盖度，由你决定何时停止。"],
  ["integrate", "HIGHLIGHT · 突出呈现", "保留该区域，并让它成为当前妆容的一部分。"],
] as const;

const polygonForSelection = (selection: {
  x: number;
  y: number;
  width: number;
  height: number;
  polygon?: NormalizedPoint[];
}) => selection.polygon?.length ? selection.polygon : ellipsePolygon(selection, 12);

export function LocalAppearanceCard({
  image,
  editor = false,
}: {
  image?: string;
  editor?: boolean;
}) {
  const nav = useNavigate();
  const currentFace = getStaticFace();
  image = currentFace?.image || image;
  const [editingId, setEditingId] = useState<string>();
  const sectionRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [saved, setSaved] = useState(getLocalAppearancePreferences);
  const [selecting, setSelecting] = useState(editor && saved.length === 0);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<NormalizedPoint[]>([]);
  const [dragIndex, setDragIndex] = useState<number>();
  const [viewport, setViewport] = useState({ width: 0, height: 0 });
  const [source, setSource] = useState({ width: 0, height: 0 });
  const [location, setLocation] = useState<LocalRegion>("局部区域");
  const [userLabel, setUserLabel] = useState("");
  const [preference, setPreference] = useState<AppearancePreference>();
  const [error, setError] = useState("");

  useEffect(() => {
    if (selecting) sectionRef.current?.scrollIntoView({ block: "start" });
  }, [selecting]);

  useEffect(() => {
    const element = canvasRef.current;
    if (!element) return;
    const update = () =>
      setViewport({ width: element.clientWidth, height: element.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [selecting, image]);

  const geometry = useMemo<MediaGeometry | undefined>(() => {
    if (!source.width || !source.height || !viewport.width || !viewport.height)
      return undefined;
    return {
      sourceWidth: source.width,
      sourceHeight: source.height,
      viewportWidth: viewport.width,
      viewportHeight: viewport.height,
      objectFit: currentFace ? "contain" : "cover",
      mirrored: currentFace?.displayMirrored ?? false,
    };
  }, [currentFace, source, viewport]);

  const faceHull = useMemo(
    () => convexHull(currentFace?.landmarks ?? []),
    [currentFace],
  );

  const draftValid =
    draft.length >= 3 && isSimplePolygon(draft) && polygonArea(draft) >= 0.00005;

  function begin(id?: string) {
    const existing = saved.find((item) => (item.id || item.region) === id);
    setEditingId(id);
    setLocation(existing?.region || "局部区域");
    setUserLabel(existing?.userLabel || "");
    setError("");
    setDraft(
      existing?.selection &&
        (currentFace
          ? isPhotoSelectionCurrent(existing, currentFace.id)
          : existing.imageSource !== "user-photo")
        ? polygonForSelection(existing.selection)
        : [],
    );
    setPreference(existing?.preference);
    setSelecting(true);
  }

  async function enter() {
    await copyPreferencePreview(image);
    nav("/face-preferences");
  }

  function remove(id: string) {
    try {
      const next = saved.filter((item) => (item.id || item.region) !== id);
      setLocalAppearancePreferences(next);
      setSaved(next);
    } catch {
      setError("未能保存，请重试。");
    }
  }

  function cancel() {
    setOpen(false);
    setSelecting(false);
    setDraft([]);
    setError("");
  }

  function eventToRaw(event: PointerEvent<HTMLElement>) {
    const canvas = canvasRef.current;
    if (!canvas || !geometry) return null;
    const rect = canvas.getBoundingClientRect();
    return displayPointToRaw(
      { x: event.clientX - rect.left, y: event.clientY - rect.top },
      geometry,
    );
  }

  function acceptPoint(point: NormalizedPoint | null) {
    if (!point) {
      setError("请在照片范围内标记区域。");
      return false;
    }
    if (faceHull.length >= 3 && !pointInPolygon(point, faceHull)) {
      setError("选点需要位于检测到的面部范围内，请在皮肤区域重新标记。");
      return false;
    }
    setError("");
    return true;
  }

  function addPoint(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("[data-selection-handle]")) return;
    const point = eventToRaw(event);
    if (!acceptPoint(point) || !point) return;
    if (draft.length >= 16) {
      setError("一个区域最多使用 16 个控制点，请拖动已有节点调整。");
      return;
    }
    setDraft((current) => [...current, point]);
  }

  function movePoint(index: number, event: PointerEvent<HTMLButtonElement>) {
    if (dragIndex !== index) return;
    const point = eventToRaw(event);
    if (!acceptPoint(point) || !point) return;
    setDraft((current) =>
      current.map((existing, pointIndex) => pointIndex === index ? point : existing),
    );
  }

  function finish() {
    if (!draftValid || !preference) return;
    try {
      const next = {
        id: editingId || crypto.randomUUID(),
        region: location,
        userLabel: userLabel.trim(),
        selection: selectionBounds(draft),
        imageSource: currentFace ? "user-photo" as const : "illustration" as const,
        imageId: currentFace?.id,
        preference,
        integrateStyle: preference === "integrate" ? "highlight" as const : null,
      };
      const updated = [
        ...saved.filter((item) => (item.id || item.region) !== editingId),
        next,
      ];
      setLocalAppearancePreferences(updated);
      setSaved(updated);
      cancel();
    } catch {
      setError("未能保存，请重试。");
    }
  }

  const toDisplay = (points: NormalizedPoint[]) =>
    geometry ? points.map((point) => rawPointToDisplay(point, geometry)) : [];

  const savedSelections = saved.filter(
    (item) =>
      item.selection &&
      (item.id || item.region) !== editingId &&
      (currentFace
        ? isPhotoSelectionCurrent(item, currentFace.id)
        : item.imageSource !== "user-photo"),
  );

  return (
    <section
      ref={sectionRef}
      className="local-appearance-card"
      id="local-appearance"
      aria-label="局部呈现偏好"
    >
      {selecting ? (
        <>
          <div className="local-card-heading">
            <div>
              <span className="selection-kicker">AREA SELECT</span>
              <h2>沿着真实区域勾勒边界</h2>
            </div>
            <small>{draft.length} / 16 个节点</small>
          </div>
          <p>依次点击区域边缘，至少放置 3 个点；拖动紫色节点可精细调整。</p>
          <div
            ref={canvasRef}
            className={`region-canvas ${currentFace ? "region-canvas-photo" : ""}`}
            role="application"
            tabIndex={0}
            aria-label="面部区域多边形编辑器"
            onPointerDown={addPoint}
            onKeyDown={(event) => {
              if ((event.key === "Backspace" || event.key === "Delete") && draft.length) {
                event.preventDefault();
                setDraft((current) => current.slice(0, -1));
              }
              if (event.key === "Escape") setDraft([]);
            }}
          >
            <img
              src={image || publicAsset("assets/face/scan-guide.png")}
              alt={image ? "本次面部画面" : "扫脸示意图"}
              draggable={false}
              onLoad={(event) => {
                setSource({
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                });
                setViewport({
                  width: event.currentTarget.clientWidth,
                  height: event.currentTarget.clientHeight,
                });
              }}
            />
            {geometry && (
              <svg
                className="selection-overlay"
                viewBox={`0 0 ${viewport.width} ${viewport.height}`}
                aria-hidden="true"
              >
                {savedSelections.map((item, index) => {
                  const points = toDisplay(polygonForSelection(item.selection!));
                  return (
                    <g key={item.id || item.region} className="saved-area-shape">
                      <polygon points={points.map((point) => `${point.x},${point.y}`).join(" ")} />
                      <text x={points[0]?.x ?? 0} y={points[0]?.y ?? 0}>{index + 1}</text>
                    </g>
                  );
                })}
                {draft.length >= 2 && (
                  draftValid ? (
                    <polygon
                      className="draft-area-shape"
                      points={toDisplay(draft).map((point) => `${point.x},${point.y}`).join(" ")}
                    />
                  ) : (
                    <polyline
                      className="draft-area-line"
                      points={toDisplay(draft).map((point) => `${point.x},${point.y}`).join(" ")}
                    />
                  )
                )}
              </svg>
            )}
            {geometry && toDisplay(draft).map((point, index) => (
              <button
                type="button"
                key={index}
                data-selection-handle
                className="selection-handle"
                aria-label={`拖动控制点 ${index + 1}`}
                style={{ left: point.x, top: point.y }}
                onPointerDown={(event) => {
                  event.stopPropagation();
                  event.currentTarget.setPointerCapture(event.pointerId);
                  setDragIndex(index);
                }}
                onPointerMove={(event) => movePoint(index, event)}
                onPointerUp={(event) => {
                  event.currentTarget.releasePointerCapture(event.pointerId);
                  setDragIndex(undefined);
                }}
                onPointerCancel={() => setDragIndex(undefined)}
              />
            ))}
          </div>
          {!currentFace && <small>这是位置示意；使用扫描照片后可在本人画面上精确标记。</small>}
          {draft.length >= 3 && !isSimplePolygon(draft) && (
            <p role="alert">边界发生交叉，请拖动节点或撤销最后一个点。</p>
          )}
          {error && <p role="alert">{error}</p>}
          <div className="local-actions">
            <Button variant="tertiary" onClick={cancel}>取消</Button>
            <Button variant="tertiary" disabled={!draft.length} onClick={() => setDraft((current) => current.slice(0, -1))}>
              撤销一点
            </Button>
            <Button variant="outline" disabled={!draft.length} onClick={() => setDraft([])}>
              重新勾勒
            </Button>
            <Button disabled={!draftValid} onClick={() => setOpen(true)}>确认区域</Button>
          </div>
        </>
      ) : (
        <>
          <div className="local-card-heading">
            <h2>局部呈现偏好</h2>
            <small>{saved.length ? `✓ 已设置 ${saved.length} 个区域` : "可选"}</small>
          </div>
          {saved.map((item, index) => (
            <div className="local-region-row" key={item.id || item.region}>
              <p>
                区域 {index + 1} · {item.userLabel || item.region} ·{" "}
                {choices.find((choice) => choice[0] === item.preference)?.[1]}
              </p>
              {editor && (
                <div className="local-actions">
                  <Button variant="tertiary" onClick={() => begin(item.id || item.region)}>调整区域 {index + 1}</Button>
                  <Button variant="tertiary" onClick={() => remove(item.id || item.region)}>删除区域 {index + 1}</Button>
                </div>
              )}
            </div>
          ))}
          {!saved.length && <p>如果有某个区域希望采用不同的上妆方式，可以由你亲自标记。</p>}
          <Button variant="tertiary" onClick={() => (editor ? begin() : void enter())}>
            {editor ? (saved.length ? "添加另一个区域" : "标记一个区域") : saved.length ? "调整" : "标记一个区域"}
          </Button>
          {error && <p role="alert">{error}</p>}
        </>
      )}
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="modal-backdrop" />
          <Dialog.Content className="modal local-preference-sheet">
            <div className="local-preference-body">
              <Dialog.Title>这个区域希望怎样呈现？</Dialog.Title>
              <Dialog.Description>选择由你决定；MIRA 不会推断或自动遮盖皮肤特征。</Dialog.Description>
              <label>
                部位（左右以本人为准）
                <select value={location} onChange={(event) => setLocation(event.target.value as LocalRegion)}>
                  {regions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <label>
                区域标签（可选）
                <input value={userLabel} maxLength={80} onChange={(event) => setUserLabel(event.target.value)} placeholder="自行描述这个区域" />
              </label>
              <fieldset className="preference-options">
                <legend className="sr-only">呈现方式</legend>
                {choices.map(([id, title, description]) => (
                  <label key={id}>
                    <input type="radio" name="local-preference" checked={preference === id} onChange={() => setPreference(id)} />
                    <span><strong>{title}</strong><small>{description}</small></span>
                  </label>
                ))}
              </fieldset>
              {error && <p role="alert">{error}</p>}
            </div>
            <div className="local-actions">
              <Button variant="tertiary" onClick={() => setOpen(false)}>返回选区</Button>
              <Button disabled={!preference} onClick={finish}>保存偏好</Button>
              <Button variant="tertiary" onClick={cancel}>今天不设置</Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
