import type { ARGuidance } from "../../types/guidance";
export function AROverlay({
  guidance,
  personalized,
}: {
  guidance: ARGuidance;
  personalized: boolean;
}) {
  const [dx, dy] = guidance.directionVector;
  const [cx, cy] = guidance.standardRegion.center;
  const [rx, ry] = guidance.standardRegion.radius;
  return (
    <svg
      className="ar-overlay"
      viewBox="0 0 100 100"
      aria-label={personalized ? "个性化区域示意" : "当前指导区域示意"}
    >
      <defs>
        <marker
          id="direction-head"
          markerWidth="4"
          markerHeight="4"
          refX="3"
          refY="2"
          orient="auto"
        >
          <path d="M0 0 L4 2 L0 4" fill="none" stroke="#c7a45d" />
        </marker>
      </defs>
      {personalized && guidance.polygon.length > 0 ? (
        <polygon
          points={guidance.polygon.map((p) => p.join(",")).join(" ")}
          fill="#c7a45d33"
          stroke="#c7a45d"
          strokeWidth=".4"
        />
      ) : (
        <ellipse
          cx={cx}
          cy={cy}
          rx={rx}
          ry={ry}
          fill="none"
          stroke="#c7a45d"
          strokeWidth=".4"
          strokeDasharray="1 1"
        />
      )}
      <line
        x1={cx}
        y1={cy - 2}
        x2={cx + dx * 13}
        y2={cy - 2 + dy * 13}
        stroke="#c7a45d"
        strokeWidth=".6"
        markerEnd="url(#direction-head)"
      />
    </svg>
  );
}
