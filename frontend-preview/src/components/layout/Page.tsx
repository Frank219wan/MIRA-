import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Link } from "react-router-dom";
export function Page({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className="page"
      initial={reduced ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <Link to="/tutorial" className="back">
        <span>灵感之旅</span>
        <span aria-hidden="true">／</span>
        <span>{eyebrow}</span>
      </Link>
      <div className="page-title">
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children}
    </motion.div>
  );
}
