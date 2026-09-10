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
          <div className="eyebrow">MIRA BEAUTY STUDIO / 映己美妆</div>
          <h1>
            <span className="hero-opening">把喜欢的美妆教程，</span>
            <br />
            变成<span className="hero-emphasis">属于你的</span>
            <br className="hero-break" />
            教程。
          </h1>
          <p>
            AI 理解妆容、你的产品，
            <br className="mobile-break" />
            以及你的面部特征。
          </p>
          <Button asChild>
            <Link to="/tutorial">
              从教程开始
              <ArrowRight size={18} />
            </Link>
          </Button>
          <div className="hero-note">
            <span className="tiny-line" />
            让灵感落在你的脸上。
          </div>
        </motion.div>
        <div className="hero-visual">
          <span className="hero-image-index">01 — 灵感，映见自己</span>
          <div className="hero-image">
            <img src="/assets/hero/hero-makeup.jpg" alt="精致眼妆灵感" />
            <div className="image-caption">
              <span>THE ART OF BEING YOU</span>
              <span>你的美，自有章法。</span>
            </div>
          </div>
          <span className="hero-side-note" aria-hidden="true">
            MIRA / A BEAUTY OF YOUR OWN
          </span>
        </div>
      </section>
      <div className="journey">
        {["Decode", "Match", "Adapt", "Coach"].map((x, i) => (
          <div key={x}>
            <span className="journey-number">0{i + 1}</span>
            <span>
              {["拆解灵感", "匹配已有", "为你调整", "陪你完成"][i]}
              <small>{x}</small>
            </span>
            {i < 3 && <ArrowRight size={20} />}
          </div>
        ))}
      </div>
    </div>
  );
}
