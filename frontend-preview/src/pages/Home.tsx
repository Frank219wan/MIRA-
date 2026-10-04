import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "../components/ui/button";
export default function Home() {
  const reduced = useReducedMotion();
  return (
    <div className="home">
      <section className="hero">
        <motion.div
          className="hero-copy"
          initial={reduced ? false : { opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
        >
          <h1>
            <span className="hero-opening">把喜欢的美妆教程，</span>
            <br />
            变成<span className="hero-emphasis">属于你的</span>
            <br className="hero-break" />
            教程。
          </h1>
          <p>
            MIRA 拆解你喜欢的美妆教程，匹配已有产品，根据面部结构调整，
            再生成可以逐步跟随的教程。
          </p>
          <Button asChild>
            <Link to="/tutorial">
              从教程开始
              <ArrowRight size={18} />
            </Link>
          </Button>
        </motion.div>
        <div className="hero-visual">
          <div className="hero-image">
            <img src="/assets/hero/hero-makeup.jpg" alt="精致眼妆灵感" />
          </div>
        </div>
      </section>
      <section className="home-process" aria-label="MIRA 使用流程">
        <div className="journey">
          {[
            ["Decode", "拆解教程"],
            ["Match", "匹配已有"],
            ["Adapt", "为你调整"],
            ["Coach", "陪你完成"],
          ].map(([label, description], i) => (
            <div key={label}>
              <span className="journey-number">0{i + 1}</span>
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
              {i < 3 && <ArrowRight size={20} />}
            </div>
          ))}
        </div>
        <p className="home-difference">
          不是推荐相似妆容，而是把你喜欢的教程改写成你能真正完成的版本。
        </p>
        <aside className="home-support">
          <span>MIRA 支持服务 · 演示</span>
          <p>
            若在教程上传、产品匹配或步骤理解中遇到问题，支持服务可协助说明。
          </p>
        </aside>
      </section>
    </div>
  );
}
