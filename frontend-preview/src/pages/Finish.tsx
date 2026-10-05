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
      title="妆容完成"
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
              ["完成教程步骤", `${data.completed} / 5`],
              ...(data.productMode === "beauty-kit"
                ? [
                    ["现有产品复用", `${data.reused} 件`],
                    ["产品能力缺口", `${data.missing.length} 项`],
                  ]
                : [["产品使用方式", "通用描述"]]),
              [
                data.exampleProfile
                  ? "AI 调整数量（示例档案）"
                  : "AI 个性化调整数量",
                `${data.adjustmentCount} 项`,
              ],
            ].map(([k, v]) => (
              <Card key={k}>
                <span>{k}</span>
                <strong>{v}</strong>
              </Card>
            ))}
          </div>
          <Card>
            <h2>属于你的操作笔记</h2>
            {data.adapted ? data.changes.map((x) => <p key={x}>{x}</p>) : null}
            <p>{data.productChange}</p>
            {data.productMode === "beauty-kit" && (
              <p>产品能力缺口：{data.missing.join(" / ") || "无"}。</p>
            )}
          </Card>
        </>
      )}
      <div className="action-row">
        <Button variant="outline" onClick={save} disabled={saved}>
          {saved ? "已保存至此浏览器" : "保存本次教程"}
        </Button>
        <Button asChild>
          <Link to="/">完成</Link>
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
