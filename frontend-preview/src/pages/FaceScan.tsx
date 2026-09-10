import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Card, Tag } from "../components/ui/primitives";
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
      eyebrow="03 / ADAPT"
      title={started ? "找到舒适的镜头位置" : "让教程，更贴合你的面部"}
      description="面部扫描用于调整教程中的位置、范围、方向和用量。"
    >
      {!started ? (
        <>
          <div className="two-columns">
            <Card>
              <span className="eyebrow">由你决定</span>
              <h2>理解特征，尊重每一种美</h2>
              <p>
                不进行颜值评分
                <br />
                不进行“缺陷”判断
                <br />
                不进行医疗诊断
              </p>
              <p>
                当前体验使用示例面部档案，不启动真实摄像头，也不采集生物特征。
              </p>
              <Tag>你也可以直接继续，获得基于产品的教程</Tag>
            </Card>
            <Card>
              <h2>扫描规范</h2>
              <ul className="scan-rules">
                {[
                  "正面自然看向镜头",
                  "面部无遮挡",
                  "光线均匀",
                  "避免逆光、彩色灯光和强滤镜",
                  "自然表情",
                  "镜头与面部基本平行",
                  "建议距离约 40–70 cm",
                ].map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </Card>
          </div>
          <div className="equal-actions">
            <Button variant="outline" onClick={start}>
              同意并开始扫描
            </Button>
            <Button variant="outline" onClick={skip}>
              暂不扫描，继续生成教程
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className="two-columns">
            <FaceViewport />
            <Card>
              <h2>取景状态</h2>
              <Tag>示例质量数据</Tag>
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
              <p>
                {error || "真实扫描能力尚未接入，继续后将查看示例面部档案。"}
              </p>
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
            <Button variant="outline" onClick={() => setStarted(false)}>
              返回扫描说明
            </Button>
            <Button variant="outline" onClick={skip}>
              暂不扫描，继续生成教程
            </Button>
          </div>
        </>
      )}
    </Page>
  );
}
