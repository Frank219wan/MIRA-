import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { JourneyNavigation } from "../tutorial/JourneyNavigation";
export function Page({
  eyebrow,
  title,
  description,
  backTo,
  progress,
  backLabel,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  backTo?: string;
  progress?: number;
  backLabel?: string;
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
      {backTo !== undefined && progress !== undefined && (
        <JourneyNavigation backTo={backTo} progress={progress} backLabel={backLabel} />
      )}
      <div className="page-title">
        <span className="page-eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children}
    </motion.div>
  );
}
