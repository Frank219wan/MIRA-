import type { MakeupAction } from "../../types/tutorial";

/** Editorial schematic only; never a measured face or an extracted tutorial frame. */
export function StepIllustration({ action }: { action?: MakeupAction }) {
  const text = `${action?.name} ${action?.area} ${action?.goal} ${action?.productRequirement}`;
  const kind = /眼线/.test(text)
    ? "liner"
    : /下眼/.test(text)
      ? "lower"
      : /提亮|珠光/.test(text)
        ? "highlight"
        : /衔接|过渡|晕染/.test(action?.name || "")
          ? "blend"
          : /眼尾|加深/.test(text)
            ? "outer"
            : /打底|上眼睑|眼皮/.test(text)
              ? "base"
              : "neutral";
  return (
    <figure className="step-illustration">
      <figcaption>{action?.name || "当前步骤"} · 操作示意</figcaption>
      <svg
        viewBox="0 0 400 280"
        role="img"
        aria-label={`${action?.name || "眼部"}操作区域示意`}
      >
        <path
          d="M68 80 Q185 28 326 74"
          fill="none"
          stroke="#454545"
          strokeWidth="4"
          strokeLinecap="round"
        />
        {kind === "base" && (
          <path d="M65 148 Q185 55 330 148 Q190 112 65 148" fill="#ddd" />
        )}
        {kind === "outer" && (
          <path
            d="M244 101 Q302 113 330 148 L248 158 Q272 130 244 101"
            fill="#c7c7c7"
          />
        )}
        {kind === "blend" && (
          <path
            d="M77 122 Q185 63 314 127"
            fill="none"
            stroke="#aaa"
            strokeWidth="18"
            strokeLinecap="round"
            strokeDasharray="2 8"
          />
        )}
        {kind === "highlight" && (
          <ellipse
            cx="198"
            cy="119"
            rx="30"
            ry="18"
            fill="#e6e6e6"
            stroke="#888"
            strokeDasharray="3 4"
          />
        )}
        <path
          d="M65 148 Q190 194 330 148"
          fill="none"
          stroke="#666"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M300 158 l8 8 M314 153 l8 7 M326 149 l8 5"
          fill="none"
          stroke="#888"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        {kind === "liner" && (
          <path
            d="M70 150 Q198 191 330 148 L348 137"
            fill="none"
            stroke="#111"
            strokeWidth="5"
            strokeLinecap="round"
          />
        )}
        {kind === "lower" && (
          <path
            d="M247 184 Q293 175 327 155"
            fill="none"
            stroke="#999"
            strokeWidth="10"
            strokeLinecap="round"
          />
        )}
        <text x="65" y="240" fontSize="13" fill="#777">
          内眼角
        </text>
        <text x="292" y="240" fontSize="13" fill="#777">
          外眼角
        </text>
      </svg>
      <p>{action?.motion}</p>
      <small>位置示意，请结合右侧说明与镜中妆效操作。</small>
    </figure>
  );
}
