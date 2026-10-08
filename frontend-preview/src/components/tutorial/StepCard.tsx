import type { MakeupAction } from "../../types/tutorial";
import { ChevronDown, MapPin, MoveUpRight } from "lucide-react";
import { CapabilityTags } from "./CapabilityTags";
const time = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
export function StepCard({ action: a }: { action: MakeupAction }) {
  return (
    <article className="step-card">
      <div className="step-number">{String(a.order).padStart(2, "0")}</div>
      <div className="step-body">
        <div className="step-title">
          <h2>{a.name}</h2>
          <span className="step-time">
            {time(a.startTime)} — {time(a.endTime)}
          </span>
        </div>
        <dl className="step-facts">
          <div>
            <dt>
              <MapPin size={12} />
              位置
            </dt>
            <dd>{a.area}</dd>
          </div>
          <div>
            <dt>产品需要</dt>
            <dd>
              <CapabilityTags value={a.productRequirement} />
            </dd>
          </div>
          <div className="step-motion">
            <dt>
              <MoveUpRight size={12} />
              操作
            </dt>
            <dd>{a.motion}</dd>
          </div>
        </dl>
        <details>
          <summary>
            <span>展开步骤</span>
            <ChevronDown size={14} />
          </summary>
          <dl className="step-expanded">
            {[
              ["目标", a.goal],
              ["工具", a.tool],
              ["强度", a.intensity],
              ["目标效果", a.targetResult],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
    </article>
  );
}
