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
          进入演示个人空间 ↗
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
      <p className="face-scan-note">
        这是保存时的教程内容，不会重新调用分析接口。
      </p>
      {tutorial.actions.map((action, i) => (
        <section className="account-section" key={action.actionId}>
          <h2>
            {String(i + 1).padStart(2, "0")} ·{" "}
            {tutorial.stepNames?.[i] || `步骤 ${i + 1}`}
          </h2>
          <p>{action.product}</p>
          <p>{action.instructions}</p>
          <p>停止条件：{action.stopWhen}</p>
          {action.personalizationSource === "backend-personalization" && (
            <p className="face-scan-note">
              {action.faceProfileSource === "scan"
                ? "基于扫描档案的后端调整"
                : "基于示例档案的后端调整"}
            </p>
          )}
        </section>
      ))}
    </Page>
  );
}
