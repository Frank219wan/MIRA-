import { PreferenceGuidance } from "../components/preferences/PreferenceGuidance";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/primitives";
import { getFinishSummary } from "../services/finish";
import { savePersonalizedTutorial } from "../services/personalizedTutorial";
import { useService } from "../hooks/useService";
export default function Finish() {
  const { data, error } = useService(getFinishSummary);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  async function save() {
    try {
      await savePersonalizedTutorial();
      setSaved(true);
    } catch {
      setSaveError("浏览器未能保存，请检查本地存储权限后重试。");
    }
  }
  return (
    <Page
      eyebrow="05 / 完成"
      title="完成啦，这是你的这一次 Look"
      backTo="/live-coach"
      progress={100}
    >
      <div className="finish-mark">
        <Check size={30} />
      </div>
      {error && <p>{error}</p>}
      {data && (
        <>
          <div className="stats">
            {[
              ["步骤完成", `${data.completed} / ${data.total}`],
              ...(data.productMode === "beauty-kit" && data.reusedSteps > 0
                ? [["使用已有产品完成", `${data.reusedSteps} / ${data.total}`]]
                : []),
              ...(!data.exampleProfile && data.adjustmentCount > 0
                ? [["面部适配", `${data.adjustmentCount} 项调整`]]
                : []),
            ].map(([k, v]) => (
              <Card key={k}>
                <span>{k}</span>
                <strong>{v}</strong>
              </Card>
            ))}
          </div>
          {(data.adapted ||
            data.localAppearanceGuidance.length > 0 ||
            data.reusedSteps > 0) && (
            <Card>
              <h2>留给下次的妆容笔记</h2>
              {data.adapted && (
                <>
                  <p>
                    {data.exampleProfile
                      ? "本次参考面部方案的调整，未使用你的扫描："
                      : "本次使用的面部调整："}
                  </p>
                  {data.changes.map((x) => (
                    <p key={x}>{x}</p>
                  ))}
                </>
              )}
              {data.reusedSteps === data.total && data.total > 0 && (
                <p>这次用已有产品完成了整个妆容。</p>
              )}
              <PreferenceGuidance guidance={data.localAppearanceGuidance} />
            </Card>
          )}
        </>
      )}
      <div className="action-row">
        <Button variant="outline" onClick={save} disabled={saved}>
          {saved ? "已保存至此浏览器" : "保存这次教程"}
        </Button>
        <Button asChild>
          <Link to="/">回到首页</Link>
        </Button>
      </div>
      {saved && (
        <p>
          <Link className="text-link" to="/account">
            前往我的教程 ↗
          </Link>
        </p>
      )}
      {saveError && <p role="alert">{saveError}</p>}
    </Page>
  );
}
