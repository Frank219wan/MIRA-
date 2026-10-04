import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/primitives";
import { FaceViewport } from "../components/face/FaceViewport";
import {
  scanFaceImages,
  setFaceConsent,
  cancelPendingFaceScan,
} from "../services/face";

import { getProductUseMode } from "../services/productMode";
export default function FaceScan() {
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
    const run = ++generation.current;
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
    const run = generation.current;
    setBusy(true);
    setError("");
    try {
      const result = await scanFaceImages(images);
      if (run !== generation.current) return;
      if (!result)
        throw new Error("未能完成扫描，请重试或跳过，继续标准教程。");
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
    const run = generation.current;
    setBusy(true);
    setError("");
    try {
      const frames: Blob[] = [];
      const canvas = document.createElement("canvas");
      for (let i = 0; i < 3; i++) {
        if (run !== generation.current) return;
        const element = video.current;
        if (!element?.videoWidth)
          throw new Error("摄像头尚未准备好，请稍后重试。");
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
        if (i < 2) await new Promise((resolve) => setTimeout(resolve, 350));
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
      title={started ? "找到舒适的镜头位置" : "让教程，更贴合你的面部"}
      backTo={productMode === "beauty-kit" ? "/matching" : "/tutorial/recipe"}
      progress={50}
    >
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
            <Button onClick={start}>同意并开始扫描</Button>
            <Button variant="outline" onClick={skip}>
              暂不扫描，继续生成教程
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className="two-columns face-scan-active">
            <FaceViewport label="面部取景" live>
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
            </FaceViewport>
            <Card>
              <h2>取景状态</h2>
              <p role="status">
                {busy
                  ? "正在采集并分析…"
                  : validFrames
                    ? `已完成扫描 · ${validFrames} 个有效画面`
                    : "正对镜头，保持面部无遮挡"}
              </p>
              {error && <p role="alert">{error}</p>}
              {validFrames ? (
                <Button onClick={() => nav("/beauty-profile")}>
                  查看面部档案
                </Button>
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
              暂不扫描，继续生成教程
            </Button>
          </div>
          <p className="face-scan-note">
            画面仅用于本次分析，处理后不保留原始图片。
          </p>
        </>
      )}
    </Page>
  );
}
