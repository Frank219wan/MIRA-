import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Page } from "../components/layout/Page";
import { StepCard } from "../components/tutorial/StepCard";
import { Button } from "../components/ui/button";
import { ReferenceImage } from "../components/ui/ReferenceImage";
import { useService } from "../hooks/useService";
import { getTutorial } from "../services/tutorial";
export default function Recipe() {
  const { data, error, notice } = useService(getTutorial);
  return (
    <Page
      eyebrow="01 / 拆解教程"
      title="你的教程已拆解"
    >
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <div className="recipe-layout">
        <section className="recipe-steps">
          <div className="section-topline">
            <span>
              妆容配方
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
        </aside>
      </div>
      <div className="recipe-next">
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
