import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, ArrowRight, LoaderCircle } from "lucide-react";
import { Page } from "../components/layout/Page";
import { Card, Progress, Placeholder, Tag } from "../components/ui/primitives";
import { Button } from "../components/ui/button";
import { useService } from "../hooks/useService";
import { getParsingStages } from "../services/tutorial";
export default function Parsing() {
  const { data, error } = useService(getParsingStages);
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (!data || index >= data.length - 1) return;
    const t = setTimeout(() => setIndex((v) => v + 1), 800);
    return () => clearTimeout(t);
  }, [data, index]);
  const done = !!data && index === data.length - 1;
  const percent = data ? Math.round((index / (data.length - 1)) * 100) : 0;
  return (
    <Page
      eyebrow="01 / DECODE"
      title={done ? "教程已准备好" : "正在解析你的教程"}
      description="读懂每一笔的用意，让灵感变成清晰的步骤。"
    >
      {error ? (
        <Card>
          <p role="alert">解析未完成，请重新开始。</p>
          <Button asChild>
            <Link to="/tutorial">返回输入</Link>
          </Button>
        </Card>
      ) : (
        <div className="parsing-studio">
          <section className="parsing-process" aria-label="教程解析进度">
            <div className="parsing-meter">
              <div className="meter-top">
                <span className="eyebrow">灵感，正在变得清晰</span>
                <span className={"status-light " + (done ? "is-done" : "")}>
                  {done ? "已完成" : "解析中"}
                </span>
              </div>
              <div className="meter-number">
                <strong>{percent}</strong>
                <span>%</span>
                <span className="meter-flower" aria-hidden="true">
                  ✳
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
                  <small>
                    {i < index || done
                      ? "已完成"
                      : i === index
                        ? "进行中"
                        : "待开始"}
                  </small>
                </li>
              ))}
            </ol>
          </section>
          <section className="parsing-preview">
            <div className="section-topline">
              <span>画面与动作</span>
              <Tag>演示解析</Tag>
            </div>
            <div className="technical-frame">
              <Placeholder label="关键画面预览" />
              <span className="frame-corner top-left" />
              <span className="frame-corner bottom-right" />
            </div>
            <div className="detection-caption">
              <span className="eyebrow">当前处理结果</span>
              <p aria-live="polite">
                {data?.[index].result || "正在准备参考素材"}
              </p>
            </div>
            <div className="frame-strip" aria-label="关键帧素材预留">
              <span>
                01 <i />
                待接入
              </span>
              <span>
                02 <i />
                待接入
              </span>
              <span>
                03 <i />
                待接入
              </span>
            </div>
            <p className="demo-footnote">
              当前展示预设解析流程，关键帧与真实识别结果待接入。
            </p>
          </section>
          <div className="parsing-bottom">
            <p>
              {done
                ? "每一步的产品、位置与手法，都已整理就绪。"
                : "正在整理这份灵感，请稍候。"}
            </p>
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
    </Page>
  );
}
