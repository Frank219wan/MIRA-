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
      title="教程已准备好"
      backTo={hasFaceProfile() ? "/beauty-profile" : "/face-scan"}
      progress={100}
    >
      <div className="included">
        <Tag>✓ 原教程已拆解</Tag>
        <Tag>
          ✓{" "}
          {context?.productMode === "beauty-kit"
            ? "产品已匹配"
            : "通用产品已准备"}
        </Tag>
        {adapted ? (
          <Tag>✓ 已加入后端面部调整</Tag>
        ) : (
          <>
            <span>当前使用标准位置与方向</span>
            <Link className="text-link" to="/face-scan">
              添加面部调整 ↗
            </Link>
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
                <p>{action.personalized.direction} · 基于猫眼预设参数</p>
              )}
            </div>
            <span className="overview-source">
              {action.productSource === "matched" ? "我的产品" : "通用描述"}
            </span>
            <Check size={17} aria-hidden="true" />
          </div>
        ))}
      </section>
      <div className="tutorial-start">
        <div>
          <h2>跟随时会逐步显示位置、方向与停止条件。</h2>
          <p>完整操作只在跟做过程中展开，随时可以重复当前步骤。</p>
        </div>
        <Button asChild onClick={resetCoach}>
          <Link to="/live-coach">
            开始跟做
            <ArrowRight size={17} />
          </Link>
        </Button>
      </div>
    </Page>
  );
}
