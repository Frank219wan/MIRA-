import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mic, RotateCcw, ArrowRight } from "lucide-react";
import { StepIllustration } from "../components/coach/StepIllustration";
import { Button } from "../components/ui/button";
import { Tag, Progress } from "../components/ui/primitives";
import { getPersonalizedTutorial } from "../services/personalizedTutorial";
import { getTutorial } from "../services/tutorial";
import {
  getCoachResponse,
  getCoachIntents,
  recordCompletedStep,
} from "../services/coach";
import type { CoachIntent } from "../types/guidance";
import { useService } from "../hooks/useService";
import { JourneyNavigation } from "../components/tutorial/JourneyNavigation";
export default function LiveCoach() {
  const { data, error } = useService(getPersonalizedTutorial);
  const { data: actions } = useService(getTutorial);
  const { data: intents } = useService(getCoachIntents);
  const [index, setIndex] = useState(0);
  const [response, setResponse] = useState("");
  const [showVoice, setShowVoice] = useState(false);
  const nav = useNavigate();
  const a = data?.[index];
  const adapted = a?.personalizationSource === "backend-personalization";
  function next() {
    if (!a) return;
    recordCompletedStep(a.actionId);
    setResponse("");
    if (index === data!.length - 1) nav("/finish");
    else setIndex((i) => i + 1);
  }
  async function ask(intent: CoachIntent) {
    if (intent === "下一步") {
      next();
      return;
    }
    try {
      const answer = await getCoachResponse(intent);
      setResponse(intent === "重复一下" ? a?.instructions || answer : answer);
    } catch {
      setResponse("暂时无法获取指导，请稍后重试。");
    }
  }
  return (
    <div className="coach-page">
      {error && <p>{error}</p>}
      {a && (
        <>
          <div className="coach-top">
            <JourneyNavigation backTo="/my-tutorial" progress={100} />
            <Tag>
              {adapted
                ? a.faceProfileSource === "mock"
                  ? "示例面部档案 · 后端调整"
                  : "已启用面部适配"
                : "标准教程区域 · 未使用面部适配"}
            </Tag>
          </div>
          <div className="coach-grid">
            <StepIllustration action={actions?.[index]} />
            <aside className="coach-instructions">
              <span className="eyebrow">
                步骤 {String(index + 1).padStart(2, "0")} /{" "}
                {String(data!.length).padStart(2, "0")}
              </span>
              <h1>{actions?.[index]?.name}</h1>
              <Progress value={((index + 1) / data!.length) * 100} />
              <h3>当前产品</h3>
              <p>{a.product}</p>
              <small className="product-source">
                {a.productSource === "matched"
                  ? "来自我的产品库"
                  : "通用产品描述"}
              </small>
              <h3>操作说明</h3>
              <p className="coach-motion">{a.instructions}</p>
              <p className="stop-note">停止条件 / {a.stopWhen}</p>
              <details className="coach-context">
                <summary>查看参考教程与调整原因</summary>
                <dl>
                  <div>
                    <dt>参考教程</dt>
                    <dd>
                      {a.reference.where} · {a.reference.direction}
                    </dd>
                  </div>
                  <div>
                    <dt>本次调整</dt>
                    <dd>{a.whyChanged}</dd>
                  </div>
                </dl>
              </details>
              <div className="coach-buttons">
                <Button
                  variant="outline"
                  onClick={() => setShowVoice((v) => !v)}
                  aria-expanded={showVoice}
                >
                  <Mic size={16} />
                  语音指令
                </Button>
                <Button variant="outline" onClick={() => ask("重复一下")}>
                  <RotateCcw size={16} />
                  重复
                </Button>
              </div>
              <p className="voice-note">
                语音识别尚未接入，可点击下方意图体验指导。
              </p>
              {showVoice && (
                <div className="intents">
                  {intents?.map((intent) => (
                    <button key={intent} onClick={() => ask(intent)}>
                      {intent}
                    </button>
                  ))}
                </div>
              )}
              {response && (
                <div role="status" className="coach-response">
                  {response}
                </div>
              )}
              <Button className="coach-next" onClick={next}>
                {index === data!.length - 1 ? "完成妆容" : "下一步"}
                <ArrowRight size={17} />
              </Button>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
