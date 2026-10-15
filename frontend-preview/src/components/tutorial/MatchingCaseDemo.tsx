import { useState } from "react";
import { eyelinerDirectCase, matchingCase } from "../../mocks/productMatchingCase";
import { StepNavigator } from "../tutorial-guide/StepNavigator";
import { Button } from "../ui/button";

const statusLabel = {
  "Best Match": "可直接使用",
  Match: "可替代",
  "Low Match → Alternative": "需要调整后替代",
  "Conditional Match / Alternative": "有条件替代",
} as const;

export function MatchingCaseDemo() {
  const [index, setIndex] = useState(0);
  const [directLiner, setDirectLiner] = useState(false);
  const step = matchingCase[index];
  const choice = step.id === "A04" && directLiner ? eyelinerDirectCase : step;
  return (
    <section className="case-demo" aria-labelledby="case-demo-title" id="week2-case">
      <div className="case-demo-heading">
        <div>
          <span className="eyebrow">五步产品替代示例</span>
          <h2 id="case-demo-title">逐步查看产品要求与替代方法</h2>
        </div>
        <p>下方是固定案例的前端演示判断。Impact 表示差异对妆效的影响程度，不是匹配分数。</p>
      </div>
      <p className="case-demo-disclaimer">演示案例 · 不是真实匹配结果。欧莱雅巴黎名称仅作近似品类参考；S01、S06、S15、S20、S25 为案例概念色，不进入产品库或匹配请求。</p>
      <StepNavigator index={index} count={matchingCase.length} onChange={setIndex} />
      <article className="case-step" key={step.id} aria-live="polite">
        <div className="case-step-header">
          <span className="case-step-id">{step.id}</span>
          <h3>{step.name}</h3>
          <span className={`case-status ${choice.status.includes("Alternative") ? "case-status-alt" : ""}`}>
            {statusLabel[choice.status]}
          </span>
        </div>
        {step.id === "A04" && (
          <div className="case-switch" role="group" aria-label="眼线产品情形">
            <button type="button" aria-pressed={directLiner} onClick={() => setDirectLiner(true)}>有专门眼线产品</button>
            <button type="button" aria-pressed={!directLiner} onClick={() => setDirectLiner(false)}>只有黑眼影和细刷</button>
          </div>
        )}
        <div className="case-step-grid">
          <div><span className="case-label">原教程要求</span><p>{step.requirement}</p></div>
          <div><span className="case-label">推荐的替代产品</span><div className="case-swatches" aria-hidden="true">{step.swatches.map((color) => <i key={color} style={{ backgroundColor: color }} />)}</div><p>{choice.kit}</p></div>
          <div><span className="case-label">为什么可以替代</span><p>{choice.difference}</p></div>
          <div><span className="case-label">产品与来源说明</span><p>{step.reference}</p><a href={step.source} target="_blank" rel="noreferrer">查看欧莱雅巴黎官方品类 ↗</a></div>
        </div>
        <div className="case-guidance"><strong>位置与使用方法</strong><p>{choice.guidance}</p><span>对妆效影响：{step.impact === "Low" ? "低" : step.impact === "Medium" ? "中" : "高"}</span></div>
      </article>
      <div className="case-pagination" aria-label="替代方案步骤操作">
        <Button variant="outline" disabled={index === 0} onClick={() => setIndex((value) => value - 1)}>上一步</Button>
        <span>第 {index + 1} 步，共 {matchingCase.length} 步</span>
        <Button disabled={index === matchingCase.length - 1} onClick={() => setIndex((value) => value + 1)}>下一步</Button>
      </div>
    </section>
  );
}
