import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, ArrowRight, LoaderCircle } from "lucide-react";
import { Card, Progress, Placeholder } from "../components/ui/primitives";
import { Button } from "../components/ui/button";
import { useService } from "../hooks/useService";
import { getParsingStages, getTutorial, isExampleTutorial } from "../services/tutorial";
import { publicAsset } from "../lib/assets";
export default function Parsing() {
  const { data, error: stagesError } = useService(getParsingStages);
  const { data: recipe, error: recipeError, notice } = useService(getTutorial);
  const error = stagesError || recipeError;
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (
      !data ||
      index >= data.length - 1 ||
      (!recipe && index >= data.length - 2)
    )
      return;
    const t = setTimeout(() => setIndex((v) => v + 1), 800);
    return () => clearTimeout(t);
  }, [data, index, recipe]);
  const done = !!recipe && !!data && index === data.length - 1;
  const percent = data ? Math.round((index / (data.length - 1)) * 100) : 0;
  return (
    <div className="page parsing-page">
      <Link className="back parsing-breadcrumb" to="/tutorial">
        灵感之旅 <span>/</span> 01 / 拆解教程
      </Link>
      {notice && <p role="status">{isExampleTutorial() ? "示例教程展示预设步骤，并非视频解析结果。" : notice}</p>}
      {error ? (
        <Card>
          <p role="alert">{error}</p>
          <Button asChild variant="tertiary">
            <Link to="/tutorial">返回输入</Link>
          </Button>
        </Card>
      ) : (
        <div className="parsing-studio">
          <section className="parsing-process" aria-label="教程解析进度">
            <div className="parsing-meter">
              <div className="meter-top">
                <span className={"status-light " + (done ? "is-done" : "")}>
                  {done ? "已完成" : "解析中"}
                </span>
              </div>
              <div className="meter-number">
                <strong>{percent}</strong>
                <span>%</span>
                <span className="meter-mark" aria-hidden="true">
                  {done ? (
                    <Check size={28} strokeWidth={1.2} />
                  ) : (
                    <svg
                      className="meter-spinner"
                      viewBox="0 0 40 40"
                      fill="none"
                    >
                      {Array.from({ length: 8 }, (_, i) => (
                        <line
                          key={i}
                          x1="20"
                          y1="4"
                          x2="20"
                          y2="11"
                          stroke="currentColor"
                          strokeWidth="1.25"
                          strokeLinecap="round"
                          opacity={1 - i * 0.1}
                          transform={`rotate(${i * 45} 20 20)`}
                        />
                      ))}
                    </svg>
                  )}
                </span>
              </div>
              <Progress value={percent} />
              <div className="meter-caption">
                <span>{data?.[index].label || "准备中"}</span>
                <span>
                  {String(index + 1).padStart(2, "0")} /{" "}
                  {String(data?.length || 7).padStart(2, "0")}
                </span>
              </div>
            </div>
            <ol className="pipeline">
              {data?.map((s, i) => (
                <li
                  key={s.id}
                  className={
                    i < index || done
                      ? "complete"
                      : i === index
                        ? "current"
                        : "pending"
                  }
                  aria-current={i === index ? "step" : undefined}
                >
                  <span className="pipeline-symbol">
                    {i < index || done ? (
                      <Check size={14} />
                    ) : i === index ? (
                      <LoaderCircle className="spin" size={14} />
                    ) : (
                      <span>{String(i + 1).padStart(2, "0")}</span>
                    )}
                  </span>
                  <span>{s.label}</span>
                </li>
              ))}
            </ol>
          </section>
          <section className="parsing-preview">
            <div className="section-topline">
              <span>画面与动作</span>
            </div>
            <div className="technical-frame">
              {isExampleTutorial() ? (
                <img
                  className="parsing-keyframes"
                  src={publicAsset("assets/tutorial/cat-smokey-steps.jpg")}
                  alt="猫系冷调小烟熏真人教程参考素材"
                />
              ) : (
                <Placeholder label="关键画面预览" />
              )}
              <span className="frame-corner top-left" />
              <span className="frame-corner bottom-right" />
            </div>
            <div className="detection-caption">
              <p aria-live="polite">
                {data?.[index].result || "正在准备参考素材"}
              </p>
            </div>
            <p className="demo-footnote">
              {isExampleTutorial()
                ? "示例教程参考素材用于说明拆解结构，并非实时解析结果。"
                : "进度为流程展示，关键画面尚未提供。"}
            </p>
          </section>
          <div className="parsing-bottom">
            {done ? (
              <Button asChild>
                <Link to="/tutorial/recipe">
                  查看拆解教程
                  <ArrowRight size={17} />
                </Link>
              </Button>
            ) : (
              <Button disabled>
                <LoaderCircle size={16} className="spin" />
                正在拆解教程
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
