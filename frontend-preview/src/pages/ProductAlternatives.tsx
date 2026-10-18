import { useLocation, useNavigate } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import { MatchingCaseDemo } from "../components/tutorial/MatchingCaseDemo";

type AlternativeLocationState = { returnTo?: string };

export default function ProductAlternatives() {
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = (location.state as AlternativeLocationState | null)?.returnTo || "/my-tutorial";

  return (
    <Page
      eyebrow="补充内容 / 产品替代"
      title="五步产品替代方案"
      description="逐步查看教程要求、示例替代产品、差异和使用方法。这里不会修改你的产品库或教程状态。"
      backTo={returnTo}
      backLabel="返回当前教程"
      progress={100}
    >
      <MatchingCaseDemo />
      <div className="action-row alternative-actions">
        <Button onClick={() => navigate(returnTo)}>返回当前教程</Button>
      </div>
    </Page>
  );
}
