import { Link } from "react-router-dom";
import { Check, Minus, ChevronDown } from "lucide-react";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Progress, Tag } from "../components/ui/primitives";
import { getMatchResult } from "../services/matching";
import { getTutorial } from "../services/tutorial";
import { useService } from "../hooks/useService";
export default function Matching() {
  const { data, error, notice } = useService(getMatchResult);
  const { data: actions } = useService(getTutorial);
  const n = data?.filter((x) => x.status !== "missing").length || 0;
  return (
    <Page
      eyebrow="02 / 产品匹配"
      title="匹配结果"
    >
      <div className="coverage">
        <span>教程覆盖率</span>
        <strong>{Math.round((n / (data?.length || 1)) * 100)}%</strong>
      </div>
      <Progress value={Math.round((n / (data?.length || 1)) * 100)} />
      {error && <p>{error}</p>}
      {data?.some((m) => m.difference.includes("接口占位结果")) && (
        <p role="status">
          当前匹配结果为接口占位，尚未评估真实产品能力。
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
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
              <h2>{actions?.find((a) => a.id === m.actionId)?.name}</h2>
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
                <p>
                  {
                    actions?.find((a) => a.id === m.actionId)
                      ?.productRequirement
                  }
                </p>
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
                <span className="eyebrow">匹配分数</span>
                <strong className="score">
                  {m.provenance.score === "frontend-fallback"
                    ? "未提供"
                    : m.score}
                  {m.provenance.score !== "frontend-fallback" && (
                    <small>/ 100 · 演示</small>
                  )}
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
        <Button asChild>
          <Link to="/face-scan">生成我的教程 →</Link>
        </Button>
      </div>
    </Page>
  );
}
