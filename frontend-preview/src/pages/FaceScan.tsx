import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/primitives";
import { FaceViewport } from "../components/face/FaceViewport";
import { getFaceScanQuality, setFaceConsent } from "../services/face";
import type { FaceScanQuality } from "../types/face";
export default function FaceScan() {
  const [started, setStarted] = useState(false);
  const [quality, setQuality] = useState<FaceScanQuality>();
  const [error, setError] = useState("");
  const nav = useNavigate();
  async function start() {
    setStarted(true);
    try {
      setQuality(await getFaceScanQuality());
    } catch {
      setError("暂时无法准备扫描示例，请重试。");
    }
  }
  function skip() {
    setFaceConsent(false);
    nav("/my-tutorial");
  }
  return (
    <Page
      eyebrow="03 / 专属教程"
      title={started ? "找到舒适的镜头位置" : "让教程，更贴合你的面部"}
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
          <p className="face-scan-note">
            当前为演示流程，不启用摄像头或采集面部画面。
          </p>
        </>
      ) : (
        <>
          <div className="two-columns face-scan-active">
            <FaceViewport />
            <Card>
              <h2>取景状态</h2>
              {quality && (
                <dl>
                  {[
                    ["亮度", `${Math.round(quality.brightness * 100)}% · 均匀`],
                    [
                      "面部角度",
                      `左右 ${quality.yaw}° / 俯仰 ${quality.pitch}° / 倾斜 ${quality.roll}°`,
                    ],
                    ["面部占比", `${quality.faceCoverage * 100}%`],
                    [
                      "遮挡",
                      quality.occlusion === 0 ? "无遮挡" : "请移开遮挡物",
                    ],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {error && <p role="alert">{error}</p>}
              <Button
                disabled={!quality?.valid}
                onClick={() => {
                  setFaceConsent(true);
                  nav("/beauty-profile");
                }}
              >
                查看面部档案
              </Button>
            </Card>
          </div>
          <div className="action-row">
            <Button variant="tertiary" onClick={() => setStarted(false)}>
              返回扫描说明
            </Button>
            <Button variant="outline" onClick={skip}>
              暂不扫描，继续生成教程
            </Button>
          </div>
          <p className="face-scan-note">
            当前为示例取景与面部档案，未启用摄像头。
          </p>
        </>
      )}
    </Page>
  );
}
