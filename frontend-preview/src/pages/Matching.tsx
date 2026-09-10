import { Link } from "react-router-dom";
import { Check, Minus, ChevronDown } from "lucide-react";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Progress, Tag } from "../components/ui/primitives";
import { getMatchResult } from "../services/matching";
import { getTutorial } from "../services/tutorial";
import { useService } from "../hooks/useService";
export default function Matching() {
  const { data, error } = useService(getMatchResult);
  const { data: actions } = useService(getTutorial);
  const n = data?.filter((x) => x.status !== "missing").length || 0;
  return (
    <Page
      eyebrow="02 / MATCH"
      title={`你的产品可以完成 ${n} / ${data?.length || 5} 个步骤`}
      description="不只匹配颜色，也理解质地和每一步真正需要的能力。"
    >
      <div className="coverage">
        <span>教程覆盖率 / Tutorial Coverage</span>
        <strong>{(n / 5) * 100}%</strong>
      </div>
      <Progress value={(n / 5) * 100} />
      {error && <p>{error}</p>}
      <div className="matching-list">
        {data?.map((m, i) => (
          <details
            className="category"
            data-status={m.status}
            key={m.actionId}
            open={m.status === "missing"}
          >
            <summary>
              <span className="step-number">0{i + 1}</span>
              <h2>{actions?.[i].name}</h2>
              <Tag tone={m.status === "matched" ? "success" : "warning"}>
                {m.status === "matched"
                  ? "已匹配"
                  : m.status === "partial"
                    ? "部分匹配"
                    : "能力缺口"}
              </Tag>
              <ChevronDown size={16} />
            </summary>
            <div className="match-detail">
              <div>
                <h3>教程需要什么</h3>
                <p>{actions?.[i].productRequirement}</p>
                <h3>最佳匹配产品</h3>
                <p>{m.bestMatch?.productName || "暂无匹配产品"}</p>
                <div className="checks">
                  {m.capabilityChecks.map((c) => (
                    <span key={c.label} data-passed={c.passed}>
                      {c.passed ? <Check size={14} /> : <Minus size={14} />}{" "}
                      {c.label}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <span className="eyebrow">匹配分数 / MATCH SCORE</span>
                <strong className="score">
                  {m.score}
                  <small>/ 100</small>
                </strong>
                <h3>差异</h3>
                <p>{m.difference}</p>
                <h3>对妆效的影响</h3>
                <p>{m.impact}</p>
                {m.missingCapability.length > 0 && (
                  <>
                    <p>缺少：{m.missingCapability.join(" / ")}</p>
                    <Button variant="ghost" disabled>
                      寻找替代产品 · 即将开放
                    </Button>
                  </>
                )}
              </div>
            </div>
          </details>
        ))}
      </div>
      <div className="action-row">
        <span>保留你的产品，调整实现方式。</span>
        <Button asChild>
          <Link to="/face-scan">生成我的教程 →</Link>
        </Button>
      </div>
    </Page>
  );
}
