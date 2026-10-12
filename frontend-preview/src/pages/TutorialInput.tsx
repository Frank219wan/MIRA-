import { StaticPhotoGuidance } from "../components/coach/StaticPhotoGuidance";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload,
  Link as LinkIcon,
  Image,
  Play,
  ArrowRight,
  Check,
} from "lucide-react";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { ReferenceImage } from "../components/ui/ReferenceImage";
import { saveTutorialInput } from "../services/tutorial";
import { uploadMediaPreview } from "../services/mediaPreview";
export default function TutorialInput() {
  const [mode, setMode] = useState("example");
  const [file, setFile] = useState<File>();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();
  const uploadRevision = useRef(0);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<{ uploadId: string; url: string; kind: "image" | "video" }>();
  async function selectFile(selected?: File) {
    const revision = ++uploadRevision.current;
    setFile(selected);
    setPreview(undefined);
    setError("");
    setUploading(!!selected);
    if (!selected) return;
    try {
      const result = await uploadMediaPreview(selected);
      if (revision === uploadRevision.current) setPreview(result);
    } catch (error) {
      if (revision === uploadRevision.current) setError(error instanceof Error ? error.message : "上传失败，请重试。");
    } finally {
      if (revision === uploadRevision.current) setUploading(false);
    }
  }
  async function go() {
    if (mode === "link" && !/^https?:\/\/\S+\.[^\s]+$/.test(url)) {
      setError("请输入完整的 http 或 https 教程链接。");
      return;
    }
    if ((mode === "video" || mode === "image") && !preview) {
      setError("请先上传文件并等待预览完成。");
      return;
    }
    await saveTutorialInput({
      kind: mode as "video" | "image" | "link" | "example",
      uploadId: mode === "image" || mode === "video" ? preview?.uploadId : undefined,
      name: mode === "example" ? "柔棕日常眼妆" : file?.name || url,
    });
    nav("/tutorial/parsing");
  }
  return (
    <Page
      eyebrow="01 / 拆解教程"
      title="从一个你喜欢的妆开始"
      backTo="/"
      progress={0}
    >
      <div className="input-grid">
        <section>
          <div className="input-tabs" role="group" aria-label="教程输入方式">
            {[
              ["video", "上传教程视频", Upload],
              ["link", "粘贴教程链接", LinkIcon],
              ["image", "上传参考图片", Image],
              ["example", "试试示例教程", Play],
            ].map(([id, label, Icon]) => (
              <button
                key={String(id)}
                aria-pressed={mode === id}
                className={mode === id ? "active" : ""}
                onClick={() => {
                  setMode(String(id));
                  uploadRevision.current++;
                  setFile(undefined);
                  setPreview(undefined);
                  setUploading(false);
                  setError("");
                }}
              >
                {typeof Icon !== "string" && <Icon size={18} />}
                <span>{String(label)}</span>
              </button>
            ))}
          </div>
          <div className={`input-panel input-panel-${mode}`}>
            {mode === "example" ? (
              <div className="example">
                <ReferenceImage
                  src="/assets/tutorial/purple-eye-look.jpg"
                  alt="紫色眼妆完整妆效参考"
                  caption="已有参考素材"
                />
                <div>
                  <span className="eyebrow">5 个步骤</span>
                  <h2>柔棕日常眼妆</h2>
                </div>
              </div>
            ) : mode === "link" ? (
              <label className="link-field">
                教程链接
                <input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://…"
                  type="url"
                />
                <small>链接仅作记录，本次将使用示例教程。</small>
              </label>
            ) : (
              <>
              {preview && <div className="uploaded-media-preview">
                {preview.kind === "image" ? <img src={preview.url} alt="已上传的教程图片" onError={() => setError("图片无法预览，请重新选择。")} /> : <video src={preview.url} controls playsInline preload="metadata" onError={() => setError("浏览器无法播放此视频，请尝试 MP4 格式。")} />}
              </div>}
              <label
                className={`upload tutorial-upload ${file ? "has-file" : ""}`}
              >
                <span className="upload-symbol">
                  {file ? (
                    <Check size={24} />
                  ) : (
                    <Upload size={24} strokeWidth={1.2} />
                  )}
                </span>
                <h3>
                  {file
                    ? file.name
                    : mode === "video"
                      ? "选择参考视频"
                      : "选择参考图片"}
                </h3>
                <p>
                  {mode === "video"
                    ? "支持 MP4 / MOV / WebM"
                    : "支持 JPG / PNG / WebP"}
                </p>
                <input
                  key={mode}
                  aria-label={
                    mode === "video" ? "选择参考视频文件" : "选择参考图片文件"
                  }
                  type="file"
                  accept={
                    mode === "video"
                      ? "video/mp4,video/quicktime,video/webm"
                      : "image/jpeg,image/png,image/webp"
                  }
                  onChange={(e) => {
                    void selectFile(e.target.files?.[0]);
                    e.target.value = "";
                  }}
                />
                <span className="file-choice">
                  {file ? "重新选择" : "选择文件"}
                  <ArrowRight size={14} />
                </span>
                <small role="status">{uploading ? "正在上传…" : preview ? "已上传，可开始解析。素材保留 1 小时。" : "上传后可预览，文件不超过 100 MB。"}</small>
              </label>
              </>
            )}
          </div>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <div className="action-row">
            <Button onClick={go} disabled={uploading}>
              开始解析教程
              <ArrowRight size={17} />
            </Button>
          </div>
        </section>
        <aside className="guidelines">
          {mode === "example" && <StaticPhotoGuidance />}
          {mode === "example" && <ReferenceImage className="tutorial-step-sheet" src="/assets/tutorial/purple-eye-steps.jpg" alt="紫色眼妆六步图解" caption="眼妆步骤参考" />}
          <h2>为了获得更清晰的拆解结果</h2>
          <ul>
            {[
              "单人出镜更容易看清操作",
              "面部和眼部清晰可见",
              "正面或半侧面",
              "建议 1–5 分钟",
              "完整展示主要上妆步骤",
            ].map((x) => (
              <li key={x}>
                <Check size={12} />
                {x}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </Page>
  );
}
