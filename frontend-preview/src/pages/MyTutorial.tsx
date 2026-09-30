import { useState } from "react";
import { Link } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Tag } from "../components/ui/primitives";
import { StepNavigator } from "../components/tutorial-guide/StepNavigator";
import { getPersonalizedTutorial } from "../services/personalizedTutorial";
import { getTutorial } from "../services/tutorial";
import { hasFaceProfile } from "../services/face";
import { resetCoach } from "../services/coach";
import { useService } from "../hooks/useService";
export default function MyTutorial() {
  const { data, error } = useService(getPersonalizedTutorial);
  const { data: actions } = useService(getTutorial);
  const [index, setIndex] = useState(0);
  const adapted = hasFaceProfile();
  const a = data?.[index];
  return (
    <Page eyebrow="03 / 专属教程" title="你的专属教程">
      <div className="included">
        <Tag>✓ 原教程</Tag>
        <Tag>✓ 我的产品</Tag>
        {adapted ? (
          <Tag>✓ 面部档案</Tag>
        ) : (
          <>
            <span>尚未使用面部适配</span>
            <Link className="text-link" to="/face-scan">
              扫描面部，进一步个性化 ↗
            </Link>
          </>
        )}
      </div>
      {error && <p>{error}</p>}
      <p className="demo-footnote">
        个性化动作为演示数据，面部数据不会自动生成适配。
      </p>
      {a && (
        <>
          <StepNavigator
            index={index}
            count={data!.length}
            onChange={setIndex}
          />
          <div className="tutorial-viewport">
            <div className="tutorial-heading">
              <span className="step-number">0{index + 1}</span>
              <h2>{actions?.find((x) => x.id === a.actionId)?.name}</h2>
            </div>
            <div className="comparison">
              <section>
                <h3>参考教程</h3>
                <p>{a.reference.where}</p>
                <strong>{a.reference.direction}</strong>
                <p>{a.reference.product}</p>
              </section>
              <section>
                <h3>为你调整</h3>
                <p>{a.personalized.where}</p>
                <strong>{a.personalized.direction}</strong>
                <p>{a.product}</p>
              </section>
            </div>
            <dl className="instruction-fields">
              {[
                ["目标", a.goal],
                ["使用", a.product],
                ["位置", a.personalized.where],
                ["操作", a.instructions],
                ["为什么这样调整", a.whyChanged],
                ["停止条件", a.stopWhen],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="action-row">
            <Button
              variant="outline"
              disabled={index === 0}
              onClick={() => setIndex((i) => i - 1)}
            >
              ← 上一步
            </Button>
            {index < data!.length - 1 ? (
              <Button onClick={() => setIndex((i) => i + 1)}>下一步 →</Button>
            ) : (
              <Button asChild onClick={resetCoach}>
                <Link to="/live-coach">开始实时指导 →</Link>
              </Button>
            )}
          </div>
        </>
      )}
    </Page>
  );
}
