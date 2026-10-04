import { useState } from "react";
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
export default function TutorialInput() {
  const [mode, setMode] = useState("example");
  const [file, setFile] = useState<File>();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();
  async function go() {
    if (mode === "link" && !/^https?:\/\/\S+\.[^\s]+$/.test(url)) {
      setError("请输入完整的 http 或 https 教程链接。");
      return;
    }
    if ((mode === "video" || mode === "image") && !file) {
      setError("请先选择一个文件。");
      return;
    }
    await saveTutorialInput({
      kind: mode as "video" | "image" | "link" | "example",
      name: mode === "example" ? "柔棕日常眼妆" : file?.name || url,
    });
    nav("/tutorial/parsing");
  }
  return (
    <Page eyebrow="01 / 拆解教程" title="添加参考教程" backTo="/" progress={0}>
      <div className="input-grid">
        <section>
          <div className="input-tabs" role="group" aria-label="教程输入方式">
            {[
              ["video", "上传视频", Upload],
              ["link", "粘贴链接", LinkIcon],
              ["image", "上传参考图片", Image],
              ["example", "使用示例教程", Play],
            ].map(([id, label, Icon]) => (
              <button
                key={String(id)}
                aria-pressed={mode === id}
                className={mode === id ? "active" : ""}
                onClick={() => {
                  setMode(String(id));
                  setFile(undefined);
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
                  src="/assets/tutorial/smokey-eye.jpg"
                  alt="烟熏眼妆参考"
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
                <small>链接仅作记录，解析使用示例数据。</small>
              </label>
            ) : (
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
                    setFile(e.target.files?.[0]);
                    setError("");
                  }}
                />
                <span className="file-choice">
                  {file ? "重新选择" : "选择文件"}
                  <ArrowRight size={14} />
                </span>
                <small>
                  文件仅用于本地选择，不会上传。解析将展示示例结果。
                </small>
              </label>
            )}
          </div>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <div className="action-row">
            <Button onClick={go}>
              开始拆解
              <ArrowRight size={17} />
            </Button>
          </div>
        </section>
        <aside className="guidelines">
          <h2>输入建议</h2>
          <ul>
            {[
              "单人教程",
              "面部和眼部清晰可见",
              "正面或半侧面",
              "建议 1–5 分钟",
              "能看到实际化妆步骤",
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
