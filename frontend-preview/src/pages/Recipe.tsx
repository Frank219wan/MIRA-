import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import { Page } from "../components/layout/Page";
import { StepCard } from "../components/tutorial/StepCard";
import { Button } from "../components/ui/button";
import { ReferenceImage } from "../components/ui/ReferenceImage";
import { useService } from "../hooks/useService";
import { getTutorial } from "../services/tutorial";
export default function Recipe() {
  const { data, error } = useService(getTutorial);
  return (
    <Page
      eyebrow="01 / DECODE"
      title="你的教程已拆解"
      description="柔棕日常眼妆，一份可以跟着做的妆容配方。"
    >
      {error && <p role="alert">{error}</p>}
      <div className="recipe-layout">
        <section className="recipe-steps">
          <div className="section-topline">
            <span>
              妆容配方 <small>MAKEUP RECIPE</small>
            </span>
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
          <div className="recipe-note">
            <span className="eyebrow">从看懂，到会画</span>
            <h2>
              先理解妆容，
              <br />
              再找到你的表达。
            </h2>
            <p>
              位置、产品能力与操作方式，
              <br />
              已整理成可以逐步跟随的配方。
            </p>
            <span className="recipe-ready">
              <Check size={14} />
              示例配方已就绪
            </span>
          </div>
        </aside>
      </div>
      <div className="recipe-next">
        <div>
          <span className="eyebrow">下一步 / MATCH</span>
          <h2>用你拥有的，画你喜欢的。</h2>
          <p>看看你的产品，能完成哪些步骤。</p>
        </div>
        <Button asChild>
          <Link to="/beauty-kit">
            匹配我的美妆工具库
            <ArrowRight size={17} />
          </Link>
        </Button>
      </div>
    </Page>
  );
}
