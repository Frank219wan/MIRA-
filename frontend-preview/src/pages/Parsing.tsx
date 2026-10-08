import { Link } from "react-router-dom";
import { Check, ArrowRight, LoaderCircle } from "lucide-react";
import { Card } from "../components/ui/primitives";
import { Button } from "../components/ui/button";
import { JourneyNavigation } from "../components/tutorial/JourneyNavigation";
import { useService } from "../hooks/useService";
import { getTutorial } from "../services/tutorial";
export default function Parsing() {
  const { data: recipe, error, notice } = useService(getTutorial);
  return (
    <div className="page parsing-page">
      <JourneyNavigation backTo="/tutorial" progress={recipe ? 25 : 0} />
      <div className="page-title">
        <h1>{recipe ? "妆容配方已准备好" : "正在读懂这个妆"}</h1>
      </div>
      {notice && <p role="status">{notice}</p>}
      <Card>
        {error ? (
          <>
            <p role="alert">解析未完成，请重新开始。</p>
            <Button asChild variant="tertiary">
              <Link to="/tutorial">返回输入 →</Link>
            </Button>
          </>
        ) : (
          <>
            <div className="parsing-meter" role="status" aria-live="polite">
              <div className="meter-top">
                {recipe ? (
                  <Check size={24} strokeWidth={1.2} />
                ) : (
                  <LoaderCircle size={28} strokeWidth={1.2} className="spin" />
                )}
              </div>
              <p>
                {recipe
                  ? `已整理 ${recipe.length} 个主要步骤`
                  : "正在整理产品与操作信息"}
              </p>
            </div>
            {recipe && (
              <Button asChild>
                <Link to="/tutorial/recipe">
                  查看妆容步骤 <ArrowRight size={17} />
                </Link>
              </Button>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
