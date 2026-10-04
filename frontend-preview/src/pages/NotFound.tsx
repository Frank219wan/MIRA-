import { Link } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
export default function NotFound() {
  return (
    <Page eyebrow="映己" title="这一页暂时没有找到">
      <Button asChild variant="tertiary">
        <Link to="/">回到首页</Link>
      </Button>
    </Page>
  );
}
