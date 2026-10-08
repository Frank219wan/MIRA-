import {
  checkScanImage,
  checkScanUploads,
  motionIssue,
  tolerateBriefScanChange,
} from "../services/scanQuality";
import { getServiceStatus } from "../services/base";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/primitives";
import { FaceViewport } from "../components/face/FaceViewport";
import {
  scanFaceImages,
  setFaceConsent,
  cancelPendingFaceScan,
  getFaceProfileDTO,
  setRememberFaceProfile,
  isRememberingFaceProfile,
} from "../services/face";

import { getProductUseMode } from "../services/productMode";
export default function FaceScan() {
  const [consented, setConsented] = useState(false);
  const consentRef = useRef(false);
  const [saved, setSaved] = useState(() => Boolean(getFaceProfileDTO()));
  const [remember, setRemember] = useState(isRememberingFaceProfile);
  const [phase, setPhase] = useState("ready");
  const [countdown, setCountdown] = useState(0);
  const [review, setReview] = useState("");
  const reviewURL = useRef("");
  function clearReview() {
    if (reviewURL.current) URL.revokeObjectURL(reviewURL.current);
    reviewURL.current = "";
    setReview("");
  }
  const [started, setStarted] = useState(false);
  const [stream, setStream] = useState<MediaStream>();
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [validFrames, setValidFrames] = useState(0);
  const video = useRef<HTMLVideoElement>(null);
  const camera = useRef<MediaStream | undefined>(undefined);
  const generation = useRef(0);
  function stopCamera() {
    camera.current?.getTracks().forEach((track) => track.stop());
    camera.current = undefined;
    setStream(undefined);
  }
  useEffect(
    () => () => {
      generation.current++;
      camera.current?.getTracks().forEach((track) => track.stop());
      cancelPendingFaceScan();
      if (reviewURL.current) URL.revokeObjectURL(reviewURL.current);
    },
    [],
  );
  useEffect(() => {
    if (video.current) video.current.srcObject = stream ?? null;
  }, [stream, started]);
  const [error, setError] = useState("");
  const nav = useNavigate();
  const productMode = getProductUseMode();
  async function start() {
    if (!consentRef.current) return;
    const run = ++generation.current;
    stopCamera();
    clearReview();
    setReady(false);
    setSaved(false);
    setRemember(false);
    setPhase("ready");
    setFaceConsent(false);
    setFaceConsent(true);
    setStarted(true);
    setError("");
    setValidFrames(0);
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      if (run !== generation.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      camera.current = media;
      setStream(media);
    } catch {
      if (run === generation.current)
        setError("无法开启摄像头，请允许访问或上传 3–20 张正面照片。");
    }
  }
  async function submit(images: Blob[]) {
    if (!consentRef.current) return;
    const run = generation.current;
    setBusy(true);
    setPhase("analyzing");
    setError("");
    try {
      setPhase("checking");
      await checkScanUploads(images);
      if (run !== generation.current) return;
      setPhase("analyzing");
      const result = await scanFaceImages(images);
      if (run !== generation.current) return;
      if (!result)
        throw new Error(
          getServiceStatus("scanFaceImages")?.error ||
            "未能完成扫描，请重试或跳过，继续基础教程。",
        );
      const validIndex =
        result.quality_information?.frames?.findIndex((frame) => frame.valid) ??
        0;
      clearReview();
      reviewURL.current = URL.createObjectURL(images[Math.max(0, validIndex)]);
      setReview(reviewURL.current);
      setPhase("complete");
      setValidFrames(result.valid_frame_count);
      stopCamera();
    } catch (e) {
      if (run === generation.current)
        setError(e instanceof Error ? e.message : "扫描失败，请重试。");
    } finally {
      if (run === generation.current) setBusy(false);
    }
  }
  async function capture() {
    if (!consentRef.current) return;
    const run = generation.current;
    setBusy(true);
    setError("");
    try {
      setPhase("checking");
      if (!video.current) throw new Error("请等待摄像头准备好。");
      const baseline = await tolerateBriefScanChange(async () => {
        if (run !== generation.current || !video.current)
          throw new Error("采集已取消");
        return checkScanImage(video.current);
      });
      let previous = baseline;
      async function checkStability() {
        if (run !== generation.current || !video.current) return;
        await tolerateBriefScanChange(async () => {
          if (run !== generation.current || !video.current)
            throw new Error("采集已取消");
          const current = await checkScanImage(video.current);
          const issue =
            motionIssue(baseline, current) || motionIssue(previous, current);
          if (issue) throw new Error(issue);
          previous = current;
        });
      }
      async function stableWait(milliseconds: number) {
        for (let elapsed = 0; elapsed < milliseconds; elapsed += 200) {
          await new Promise((resolve) =>
            setTimeout(resolve, Math.min(200, milliseconds - elapsed)),
          );
          if (run !== generation.current) return;
          await checkStability();
        }
      }
      if (run !== generation.current) return;
      setPhase("countdown");
      for (let i = 3; i > 0; i--) {
        if (run !== generation.current) return;
        setCountdown(i);
        await stableWait(1000);
      }
      setPhase("capturing");
      const frames: Blob[] = [];
      const canvas = document.createElement("canvas");
      for (let i = 0; i < 5; i++) {
        if (run !== generation.current) return;
        const element = video.current;
        if (!element?.videoWidth)
          throw new Error("摄像头尚未准备好，请稍后重试。");
        await checkStability();
        if (run !== generation.current) return;
        canvas.width = element.videoWidth;
        canvas.height = element.videoHeight;
        canvas.getContext("2d")!.drawImage(element, 0, 0);
        frames.push(
          await new Promise<Blob>((resolve, reject) =>
            canvas.toBlob(
              (blob) =>
                blob ? resolve(blob) : reject(new Error("无法采集画面")),
              "image/jpeg",
              0.9,
            ),
          ),
        );
        if (i < 4) await stableWait(500);
      }
      if (run === generation.current) await submit(frames);
    } catch (e) {
      if (run === generation.current)
        setError(e instanceof Error ? e.message : "采集失败，请重试。");
    } finally {
      if (run === generation.current) setBusy(false);
    }
  }
  function leave() {
    generation.current++;
    stopCamera();
    clearReview();
    setSaved(false);
    setRemember(false);
    setValidFrames(0);
    setFaceConsent(false);
    setBusy(false);
    setReady(false);
  }
  function skip() {
    leave();
    nav("/my-tutorial");
  }
  return (
    <Page
      eyebrow="03 / 专属教程"
      title={started ? "找到舒适的镜头位置" : "让教程更贴合你的面部"}
      backTo={productMode === "beauty-kit" ? "/matching" : "/tutorial/recipe"}
      progress={50}
    >
      {!started && (
        <p>
          <Link className="text-link" to="/face-preferences">
            设置局部呈现偏好 ↗
          </Link>
        </p>
      )}
      <details className="face-scan-note">
        <summary>隐私与图片使用说明</summary>
        <p>
          同意后才会开启摄像头或处理你选择的照片。画面先在浏览器检查，再发送到扫描服务计算面部数值；服务处理结束后清理原图，本页回看图片在离开后释放。面部数值仅用于调整教程的位置、范围与方向，不用于身份识别。只有另行勾选保留，数值档案才会在当前浏览器会话中保存。
        </p>
        <p>
          取消同意将停止采集并清除本地面部数据；已发送的请求可能仍会完成服务器临时处理，但返回结果不会继续使用。不扫描也可使用基础教程。
        </p>
      </details>
      <p>
        <label className="scan-consent">
          <input
            type="checkbox"
            checked={consented}
            onChange={(event) => {
              const accepted = event.target.checked;
              consentRef.current = accepted;
              setConsented(accepted);
              if (!accepted) {
                leave();
                setStarted(false);
              }
            }}
          />
          <span>
            我已阅读并同意隐私与图片使用说明，允许本次采集和分析面部画面，用于调整教程。
          </span>
        </label>
      </p>
      {!started ? (
        <>
          <div className="two-columns face-scan-intro">
            <Card className="scan-guide-card">
              <img
                className="scan-guide-image"
                src="/assets/face/scan-guide.png"
                alt="正对镜头、光线均匀且面部无遮挡的扫描姿势示意"
              />
              <p>面部信息仅用于调整教程中的位置、范围与方向。</p>
            </Card>
            <Card>
              <h2>取景建议</h2>
              <ul className="scan-rules">
                {[
                  "正对镜头",
                  "面部无遮挡",
                  "均匀自然光",
                  "距离约 40–70 cm",
                ].map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </Card>
          </div>
          <div className="equal-actions">
            {saved && (
              <Button
                disabled={!consented}
                onClick={() => nav("/beauty-profile")}
              >
                使用本次面部档案
              </Button>
            )}
            <Button
              disabled={!consented}
              variant={saved ? "outline" : "default"}
              onClick={start}
            >
              {saved ? "重新扫描" : "开始面部适配"}
            </Button>
            {saved && (
              <Button variant="tertiary" onClick={leave}>
                清除面部档案
              </Button>
            )}
            <Button variant="outline" onClick={skip}>
              暂时跳过
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className="two-columns face-scan-active">
            <div>
              {busy && phase === "countdown" && (
                <div
                  className="scan-countdown"
                  role="status"
                  aria-live="polite"
                >
                  {countdown}
                </div>
              )}
              <FaceViewport label="面部取景" live>
                {review ? (
                  <img
                    className="scan-review"
                    src={review}
                    alt="本次有效画面回看"
                  />
                ) : (
                  <>
                    <video
                      ref={video}
                      autoPlay
                      playsInline
                      muted
                      onLoadedData={() => setReady(true)}
                      style={{
                        width: "100%",
                        maxHeight: 420,
                        objectFit: "contain",
                        transform: "scaleX(-1)",
                      }}
                    />
                    {stream && (
                      <div className="scan-position-guide" aria-hidden="true" />
                    )}
                  </>
                )}
              </FaceViewport>
            </div>
            <Card>
              <h2>取景状态</h2>
              <p role="status">
                {busy
                  ? phase === "countdown"
                    ? "保持正面，即将拍摄"
                    : phase === "capturing"
                      ? "正在拍摄，请保持不动"
                      : phase === "checking"
                        ? "正在检查取景…"
                        : "正在分析画面…"
                  : validFrames
                    ? "已完成扫描"
                    : "对齐取景框，保持正面与自然表情"}
              </p>
              {!validFrames && !busy && (
                <p className="face-scan-note">
                  先检查亮度、细节和人脸取景，通过后开始倒计时。请自行确认眼部无遮挡。
                </p>
              )}
              {error && <p role="alert">{error}</p>}
              {validFrames ? (
                <>
                  <p className="face-scan-note">
                    照片用于计算眼部位置与比例，在此仅供回看，离开页面后释放。后续教程不展示照片，只使用计算出的数值调整眼线方向等操作。
                  </p>
                  <p>
                    <label className="scan-consent">
                      <input
                        type="checkbox"
                        checked={remember}
                        onChange={(event) => {
                          setRememberFaceProfile(event.target.checked);
                          setRemember(event.target.checked);
                        }}
                      />
                      <span>
                        可选：在当前浏览器会话保留面部数值，便于换教程时复用；不保存照片。
                      </span>
                    </label>
                  </p>
                  <div className="action-row">
                    <Button
                      disabled={!consented}
                      onClick={() => nav("/beauty-profile")}
                    >
                      查看面部档案
                    </Button>
                    <Button variant="outline" onClick={start}>
                      重新扫描
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <Button
                    disabled={busy || !stream || !ready}
                    onClick={capture}
                  >
                    采集并分析
                  </Button>
                  <p>
                    <label className="text-link">
                      上传 3–20 张照片
                      <input
                        aria-label="上传面部照片"
                        type="file"
                        accept="image/*"
                        multiple
                        disabled={busy}
                        onChange={(event) => {
                          const files = Array.from(event.target.files ?? []);
                          event.target.value = "";
                          if (files.length) void submit(files);
                        }}
                      />
                    </label>
                  </p>
                </>
              )}
            </Card>
          </div>
          <div className="action-row">
            <Button
              variant="tertiary"
              onClick={() => {
                leave();
                setStarted(false);
              }}
            >
              返回扫描说明
            </Button>
            <Button variant="outline" onClick={skip}>
              暂时跳过
            </Button>
          </div>
          <p className="face-scan-note">
            原始图片不长期保存；仅在你选择后保留本次会话的数值档案。
          </p>
        </>
      )}
    </Page>
  );
}
