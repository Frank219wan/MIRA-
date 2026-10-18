import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "../components/ui/button";
import { publicAsset } from "../lib/assets";
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
            <img src={publicAsset("assets/hero/beauty-adaptation.webp")} alt="面部妆容位置与方向示意" />
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
          <img src={publicAsset("assets/hero/beauty-scan.jpg")} alt="面部适配与局部区域呈现示意" loading="lazy" />
        </div>
        <section className="home-human-value" aria-labelledby="home-human-value-title">
          <span className="eyebrow">WHY MIRA</span>
          <div className="home-human-value-heading">
            <h2 id="home-human-value-title">同一份灵感，也应该有适合你的画法。</h2>
            <p>
              教程展示别人如何完成妆容，MIRA 把关键步骤、产品需求与面部特点重新整理成你能跟随的方法。从参考妆容到实际完成，让每一步都有清晰的画法。
            </p>
          </div>
          <div className="home-human-value-points">
            <article>
              <span>01</span>
              <h3>保留自己的表达</h3>
              <p>一条妆教可以生长出不同的美学表达。你可以借鉴妆容，也能保留自己的五官特点和审美选择。</p>
            </article>
            <article>
              <span>02</span>
              <h3>分享由你决定</h3>
              <p>完成妆容后是否分享，由你主动选择。面部数据不会默认公开。</p>
            </article>
          </div>
        </section>
        <aside className="home-support">
          <span>使用帮助</span>
          <p>暂不添加产品或面部信息，也可以使用基础指导开始跟妆。</p>
        </aside>
      </section>
    </div>
  );
}
