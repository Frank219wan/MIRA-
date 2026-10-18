import { PreferenceGuidance } from "../components/preferences/PreferenceGuidance";
import { Link, useParams } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { getSavedTutorials, getDemoUser } from "../services/userCenter";
export default function SavedTutorial() {
  const { id } = useParams();
  const tutorial = getSavedTutorials().find((t) => t.id === id);
  if (!getDemoUser())
    return (
      <Page eyebrow="个人中心" title="我的教程" backTo="/account">
        <Link className="text-link" to="/account">
          进入本机个人空间 ↗
        </Link>
      </Page>
    );
  if (!tutorial)
    return (
      <Page eyebrow="个人中心" title="教程已移除或未保存" backTo="/account">
        <Link className="text-link" to="/account">
          返回我的教程 ↗
        </Link>
      </Page>
    );
  return (
    <Page title={tutorial.title} eyebrow="已保存教程" backTo="/account">
      <p className="face-scan-note">这是保存时的教程与偏好。</p>
      <PreferenceGuidance guidance={tutorial.localAppearanceGuidance || []} />
      {tutorial.actions.map((action, i) => (
        <section className="account-section" key={action.actionId}>
          <h2>
            {String(i + 1).padStart(2, "0")} ·{" "}
            {tutorial.stepNames?.[i] || `步骤 ${i + 1}`}
          </h2>
          <p>{action.product}</p>
          <p>{action.instructions}</p>
          <p>做到这里就可以：{action.stopWhen}</p>
          {action.personalizationSource === "backend-personalization" && (
            <p className="face-scan-note">
              {action.faceProfileSource === "scan"
                ? "使用了扫描档案"
                : "参考面部方案 · 未使用你的扫描"}
            </p>
          )}
        </section>
      ))}
    </Page>
  );
}
