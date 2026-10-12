import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Page } from "../components/layout/Page";
import { StepCard } from "../components/tutorial/StepCard";
import { Button } from "../components/ui/button";
import { ReferenceImage } from "../components/ui/ReferenceImage";
import { useService } from "../hooks/useService";
import { getTutorial } from "../services/tutorial";
import { setProductUseMode } from "../services/productMode";
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
      {notice && <p role="status">{notice}</p>}
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
            src="/assets/tutorial/purple-eye-look.jpg"
            alt="已有眼妆参考素材"
            caption="妆面参考 · 非解析画面"
          />
        <ReferenceImage className="tutorial-step-sheet" src="/assets/tutorial/purple-eye-steps.jpg" alt="紫色眼妆六步图解" caption="眼妆步骤参考 · 非解析画面" />
        </aside>
      </div>
      <div className="recipe-next">
        <div>
          <span className="eyebrow">选择产品方式</span>
          <h2>你想怎样准备这份教程？</h2>
          <p>可以匹配已有产品，也可以直接使用步骤中的产品需求。</p>
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
          <Button asChild variant="outline">
            <Link to="/face-scan" onClick={() => setProductUseMode("generic")}>
              暂时不录入
              <ArrowRight size={17} />
            </Link>
          </Button>
        </div>
      </div>
    </Page>
  );
}
