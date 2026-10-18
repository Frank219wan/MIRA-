import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Page } from "../components/layout/Page";
import { StepCard } from "../components/tutorial/StepCard";
import { Button } from "../components/ui/button";
import { ReferenceImage } from "../components/ui/ReferenceImage";
import { useService } from "../hooks/useService";
import { getTutorial, isExampleTutorial } from "../services/tutorial";
import { setProductUseMode } from "../services/productMode";
import { publicAsset } from "../lib/assets";
export default function Recipe() {
  const { data, error, notice } = useService(getTutorial);
  return (
    <Page
      eyebrow="01 / 拆解教程"
      title="这个妆是这样完成的"
      description={
        data
          ? `已整理 ${data.length} 个关键步骤，可以先查看完整流程。`
          : undefined
      }
      backTo="/tutorial"
      progress={25}
    >
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{isExampleTutorial() ? "示例教程展示预设步骤，并非视频解析结果。" : notice}</p>}
      <div className="recipe-layout">
        <section className="recipe-steps">
          <div className="section-topline">
            <span>妆容配方</span>
            <span>{data?.length || "—"} 个步骤</span>
          </div>
          {data?.map((a) => (
            <StepCard key={a.id} action={a} />
          ))}
        </section>
        <aside className="recipe-aside">
          <ReferenceImage
            src={publicAsset("assets/tutorial/cat-smokey-synthetic-front.jpg")}
            alt="猫系冷调小烟熏正脸妆效参考"
            caption="合成妆面参考 · 非解析画面"
          />
          <ReferenceImage
            className="tutorial-step-sheet"
            src={publicAsset("assets/tutorial/cat-smokey-synthetic-steps.jpg")}
            alt="猫系冷调小烟熏六步合成图解"
            caption="合成眼妆步骤参考 · 非解析画面"
          />
        </aside>
      </div>
      <div className="recipe-next">
        <div>
          <span className="eyebrow">选择产品方式</span>
          <h2>你想怎样准备这份教程？</h2>
          <p>可以先匹配已有产品，也可以使用通用产品需求，直接进入面部扫描。</p>
        </div>
        <div className="product-path-actions">
          <Button asChild variant="outline">
            <Link
              to="/beauty-kit"
              onClick={() => setProductUseMode("beauty-kit")}
            >
              匹配我的产品
              <ArrowRight size={17} />
            </Link>
          </Button>
          <Button asChild>
            <Link to="/face-scan" onClick={() => setProductUseMode("generic")}>
              继续面部扫描
              <ArrowRight size={17} />
            </Link>
          </Button>
        </div>
      </div>
    </Page>
  );
}
