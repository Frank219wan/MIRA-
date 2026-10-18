import type { ReactNode } from "react";
import { ScanLine } from "lucide-react";
export const Card = ({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) => <section className={"card " + className}>{children}</section>;
export const Tag = ({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning";
}) => <span className={`tag tag-${tone}`}>{children}</span>;
export const Progress = ({ value }: { value: number }) => (
  <div
    className="progress"
    role="progressbar"
    aria-label="当前进度"
    aria-valuenow={value}
    aria-valuemin={0}
    aria-valuemax={100}
  >
    <span style={{ width: `${value}%` }} />
  </div>
);
/** Replace the content slot with service-backed media when available. No synthetic technical imagery. */
export const Placeholder = ({ label }: { label: string }) => (
  <div className="placeholder">
    <span className="placeholder-icon" aria-hidden="true">
      <ScanLine size={23} strokeWidth={1} />
    </span>
    <span>{label}</span>
    <small>素材待补充</small>
  </div>
);
