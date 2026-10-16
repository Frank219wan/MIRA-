import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "../components/ui/button";
export default function Home() {
  const reduced = useReducedMotion();
  return (
    <div className="home">
      <section className="hero hero-editorial">
        <motion.div
          className="hero-copy"
          initial={reduced ? false : { opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
        >
          <h1>
            <span className="hero-opening">把喜欢的妆，</span>
            <br />
            变成<span className="hero-emphasis">你的画法。</span>
            <br className="hero-break" />
          </h1>
          <p>
            从喜欢的教程开始，读懂关键步骤，选择已有产品，并结合面部设置生成可跟随的上妆指导。
          </p>
          <Button asChild>
            <Link to="/tutorial">
              开始制作我的教程
              <ArrowRight size={18} />
            </Link>
          </Button>
        </motion.div>
        <div className="hero-visual">
          <div className="hero-image">
            <img src="/assets/hero/beauty-adaptation.webp" alt="面部妆容位置与方向示意" />
          </div>
        </div>
      </section>
      <section className="home-process" aria-label="MIRA 使用流程">
        <div className="journey">
          {[
            ["DECODE", "读懂教程", "整理步骤、产品特性与操作方式"],
            ["MATCH", "匹配产品", "从美妆工具库中寻找适合的选择"],
            ["ADAPT", "适配面部", "结合面部设置调整位置与方向"],
            ["COACH", "实时指导", "跟随步骤示意与操作提示完成妆容"],
          ].map(([label, description, detail], i) => (
            <div key={label}>
              <span className="journey-number">0{i + 1}</span>
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
                <small className="process-detail">{detail}</small>
              </span>
              {i < 3 && <ArrowRight size={20} />}
            </div>
          ))}
        </div>
        <div className="home-feature-image">
          <img src="/assets/hero/beauty-scan.jpg" alt="面部适配与局部区域呈现示意" loading="lazy" />
        </div>
        <p className="home-difference">
          从参考妆容到实际完成，让每一步都有清晰的画法。
        </p>
        <aside className="home-support">
          <span>使用帮助</span>
          <p>暂不添加产品或面部信息，也可以使用基础指导开始跟妆。</p>
        </aside>
      </section>
    </div>
  );
}
