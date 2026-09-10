import type { ReactNode } from "react";
export function FaceViewport({
  children,
  label = "面部画面预留区域",
}: {
  children?: ReactNode;
  label?: string;
}) {
  return (
    <div className="face-viewport">
      <div className="camera-caption">
        <span className="camera-dot" />
        {label}
        <span>演示画面</span>
      </div>
      {/* Replace this neutral guide with a consented video stream after camera integration. */}
      <svg viewBox="0 0 100 100" className="face-outline" aria-hidden="true">
        <path d="M34 22 Q50 9 66 22 Q78 35 68 65 Q61 83 50 85 Q39 83 32 65 Q22 35 34 22Z" />
        <path d="M34 43 Q40 39 45 43 M55 43 Q61 39 67 43 M50 43 L47 60 L53 60 M42 69 Q50 73 58 69" />
        <path className="guide-dash" d="M20 43 H80 M50 12 V88" />
      </svg>
      <div className="viewport-note">摄像头尚未接入 · 不会采集面部画面</div>
      {children}
    </div>
  );
}
