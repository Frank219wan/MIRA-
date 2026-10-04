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
      title="你的教程已拆解"
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
            src="/assets/tutorial/smokey-eye.jpg"
            alt="已有眼妆参考素材"
            caption="妆面参考 · 非解析画面"
          />
        </aside>
      </div>
      <div className="recipe-next">
        <div>
          <span className="eyebrow">选择产品方式</span>
          <h2>你想怎样准备这份教程？</h2>
          <p>可以匹配已有产品，也可以直接使用无品牌指向的通用描述。</p>
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
              暂不匹配，使用通用产品
              <ArrowRight size={17} />
            </Link>
          </Button>
        </div>
      </div>
    </Page>
  );
}
