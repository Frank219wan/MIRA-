import { PreferenceGuidance } from "../components/preferences/PreferenceGuidance";
import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Tag } from "../components/ui/primitives";
import { getPersonalizedTutorialContext } from "../services/personalizedTutorial";
import { getTutorial } from "../services/tutorial";
import { hasFaceProfile } from "../services/face";
import { resetCoach } from "../services/coach";
import { useService } from "../hooks/useService";

export default function MyTutorial() {
  const { data: context, error } = useService(getPersonalizedTutorialContext);
  const { data: tutorial } = useService(getTutorial);
  const actions = context?.actions;
  const adapted =
    actions?.some(
      (a) => a.personalizationSource === "backend-personalization",
    ) ?? false;

  return (
    <Page
      eyebrow="03 / 准备完成"
      title="你的教程准备好了"
      backTo={hasFaceProfile() ? "/beauty-profile" : "/face-scan"}
      progress={100}
    >
      <p>
        {actions
          ? `${actions.length} 个步骤已整理，可查看产品选择与面部设置。`
          : "正在整理教程"}
      </p>
      <Link className="text-link" to="/face-scan">
        调整面部设置 ↗
      </Link>
      <div className="included">
        <Tag>✓ 教程步骤已解析</Tag>
        <Tag>
          ✓{" "}
          {context?.productMode === "beauty-kit"
            ? "已整理产品选择"
            : "产品需求已整理"}
        </Tag>
        {adapted ? (
          <Tag>
            {context?.provenance.personalizationFace === "mock"
              ? "参考面部方案 · 未使用你的扫描"
              : "✓ 已应用扫描档案"}
          </Tag>
        ) : (
          <>
            <span>使用基础位置指导</span>
          </>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      <section className="tutorial-overview" aria-label="教程步骤概览">
        <div className="section-topline">
          <span>开始前确认</span>
          <span>{actions?.length || "—"} 个步骤</span>
        </div>
        {actions?.map((action, index) => (
          <div className="overview-step" key={action.actionId}>
            <span className="step-number">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <h2>
                {tutorial?.find((item) => item.id === action.actionId)?.name ||
                  `步骤 ${index + 1}`}
              </h2>
              <p>{action.product}</p>
              {action.personalizationSource === "backend-personalization" && (
                <>
                  <p>{action.personalized.direction} · 相比基础猫眼方案</p>
                  <details className="scan-adjustment">
                    <summary>查看本次调整</summary>
                    <p>相比基础猫眼方案，本次调整如下：</p>
                    <dl>
                      {action.adjustmentDetails?.map((adjustment, i) => (
                        <div key={i}>
                          <dt>{adjustment.label}</dt>
                          <dd>
                            {adjustment.description}
                            <br />
                            依据：{adjustment.basis}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                </>
              )}
            </div>
            <span className="overview-source">
              {action.productSource === "matched" ? "我的产品" : "产品需求"}
            </span>
            <Check size={17} aria-hidden="true" />
          </div>
        ))}
      </section>
      <PreferenceGuidance guidance={context?.localAppearanceGuidance || []} />
      <Link className="text-link" to="/face-preferences">
        调整局部呈现偏好 ↗
      </Link>
      <div className="tutorial-start">
        <div>
          <h2>跟随步骤，确认位置、方向与完成效果。</h2>
          <p>随时可以重复当前步骤。</p>
        </div>
        <Button asChild onClick={resetCoach}>
          <Link to="/live-coach">
            开始跟妆
            <ArrowRight size={17} />
          </Link>
        </Button>
      </div>
    </Page>
  );
}
