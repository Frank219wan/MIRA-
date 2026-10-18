import type { ReactNode } from "react";
import type { MakeupAction } from "../../types/tutorial";
import type { PersonalizedAction } from "../../types/guidance";
import { guideKindFor, guideNotes, type GuideKind } from "./stepIllustrationModel";

function EyeCanvas({ kind, children }: { kind: GuideKind; children: ReactNode }) {
  const clipId = `eye-opening-${kind}`;
  const arrowId = `guide-arrow-${kind}`;
  return (
    <svg className="eye-tech-guide" viewBox="0 0 520 360" role="img" aria-label={guideNotes[kind]}>
      <defs>
        <clipPath id={clipId}><path d="M78 213 C150 139 280 125 433 202 C334 264 181 271 78 213 Z" /></clipPath>
        <marker id={arrowId} markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
          <path d="M1 1 L7 4.5 L1 8" fill="none" stroke="#76515e" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" />
        </marker>
        <linearGradient id={`base-wash-${kind}`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#ad746c" stopOpacity=".56" /><stop offset=".58" stopColor="#d4a198" stopOpacity=".36" /><stop offset="1" stopColor="#ead0c8" stopOpacity=".08" />
        </linearGradient>
        <linearGradient id={`outer-depth-${kind}`} x1="1" y1=".7" x2="0" y2=".35">
          <stop offset="0" stopColor="#65443f" stopOpacity=".76" /><stop offset=".5" stopColor="#936861" stopOpacity=".48" /><stop offset="1" stopColor="#c9988e" stopOpacity=".04" />
        </linearGradient>
        <radialGradient id={`lid-glow-${kind}`} cx="50%" cy="52%" r="54%">
          <stop offset="0" stopColor="#fff2cf" stopOpacity=".95" /><stop offset=".35" stopColor="#d9b27d" stopOpacity=".7" /><stop offset="1" stopColor="#c39372" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`lower-shadow-${kind}`} x1="1" y1="0" x2="0" y2="0">
          <stop offset="0" stopColor="#78534d" stopOpacity=".72" /><stop offset=".65" stopColor="#9c746d" stopOpacity=".38" /><stop offset="1" stopColor="#c49c94" stopOpacity=".06" />
        </linearGradient>
      </defs>
      <path className="eye-guide-brow" d="M93 87 C188 38 331 48 433 103" />
      <path className="eye-guide-crease" d="M103 158 C191 91 330 95 415 164" />
      <path className="eye-guide-skin" d="M78 213 C126 126 200 102 270 105 C349 108 405 148 433 202 C340 181 170 180 78 213 Z" />
      <g clipPath={`url(#${clipId})`}>
        <rect x="72" y="130" width="370" height="145" fill="#fbf7f3" />
        <ellipse cx="267" cy="207" rx="55" ry="54" fill="#b99680" />
        <ellipse cx="267" cy="207" rx="28" ry="28" fill="#5d463b" />
        <ellipse cx="267" cy="207" rx="12" ry="12" fill="#241d1b" />
        <circle cx="250" cy="189" r="7" fill="rgba(255,255,255,.72)" />
      </g>
      {children}
      <path className="eye-guide-upper" d="M78 213 C150 139 280 125 433 202" />
      <path className="eye-guide-lower" d="M78 213 C181 271 334 264 433 202" />
      <circle className="eye-guide-corner" cx="78" cy="213" r="3" /><circle className="eye-guide-corner" cx="433" cy="202" r="3" />
      <g className="eye-guide-labels"><text x="54" y="250">内眼角</text><text x="226" y="82">眼窝</text><text x="214" y="293">睫毛根部</text><text x="405" y="246">外眼角</text></g>
    </svg>
  );
}

function Guide({ kind, parameters = {} }: { kind: GuideKind; parameters?: Record<string, number> }) {
  const arrow = `url(#guide-arrow-${kind})`;
  const lowerRange = Math.max(0.65, Math.min(1.25, parameters.range_factor ?? 1));
  const lowerStart = 425 - 195 * lowerRange;
  const lowerOpacity = Math.max(0.5, Math.min(1, parameters.intensity_factor ?? 1));
  const extension = Math.max(0.7, Math.min(1.35, parameters.extension_factor ?? 1));
  const wingLength = 33 * extension;
  const direction = Math.max(0, Math.min(25, parameters.direction_angle_deg ?? 10));
  const wingX = 433 + wingLength;
  const wingY = 202 - Math.tan(direction * Math.PI / 180) * wingLength;
  if (kind === "base") return <EyeCanvas kind={kind}>
    <path className="guide-base-zone" d="M85 207 C157 140 281 127 429 200 C404 165 344 124 263 119 C186 115 120 145 85 207 Z" fill={`url(#base-wash-${kind})`} />
    <path className="guide-transition-band" d="M112 158 C202 104 325 105 401 163" />
    <g className="guide-arrows" markerEnd={arrow}><path d="M155 194 C157 169 169 148 185 130" /><path d="M252 174 C256 148 266 126 282 110" /><path d="M341 175 C358 157 374 144 394 135" /></g>
  </EyeCanvas>;
  if (kind === "outer") return <EyeCanvas kind={kind}>
    <path className="guide-soft-base" d="M91 207 C170 148 291 139 421 199 C375 161 312 133 235 137 C174 139 123 163 91 207 Z" />
    <path className="guide-outer-zone" d="M331 143 C380 149 417 174 433 202 C399 190 374 190 338 198 C360 178 356 160 331 143 Z" fill={`url(#outer-depth-${kind})`} />
    <path className="guide-outer-v" d="M354 151 L425 201 L345 194" />
    <g className="guide-arrows" markerEnd={arrow}><path d="M365 184 C390 168 407 151 422 130" /><path d="M346 174 C371 155 386 139 400 121" /></g>
  </EyeCanvas>;
  if (kind === "highlight") return <EyeCanvas kind={kind}>
    <path className="guide-matte-base" d="M91 207 C170 148 291 139 421 199 C357 166 310 143 250 139 C181 135 126 164 91 207 Z" />
    <ellipse className="guide-highlight-zone" cx="267" cy="163" rx="61" ry="45" fill={`url(#lid-glow-${kind})`} />
    <g className="guide-sparkles"><path d="M267 126 V143 M258.5 134.5 H275.5" /><path d="M231 151 V161 M226 156 H236" /><path d="M304 153 V165 M298 159 H310" /></g>
    <g className="guide-tap-marks"><circle cx="249" cy="170" r="3" /><circle cx="267" cy="176" r="3" /><circle cx="286" cy="169" r="3" /></g>
  </EyeCanvas>;
  if (kind === "lower") return <EyeCanvas kind={kind}>
    <path className="guide-lower-boundary" d={`M${lowerStart - 5} 259 C304 260 377 236 426 205`} />
    <path className="guide-lower-zone" d={`M${lowerStart} 253 C307 253 376 231 425 203`} stroke={`url(#lower-shadow-${kind})`} opacity={lowerOpacity} />
    <g className="guide-arrows" markerEnd={arrow}><path d="M407 224 C377 239 343 247 310 250" /><path d="M342 252 C315 257 287 258 260 256" /></g>
  </EyeCanvas>;
  if (kind === "liner") return <EyeCanvas kind={kind}>
    <path className="guide-liner" d={`M102 199 C184 147 304 139 419 192 C426 195 431 198 433 202 L${wingX} ${wingY} L435 208 C319 158 188 165 102 205 Z`} />
    <circle className="guide-liner-start" cx="103" cy="202" r="6" />
    <g className="guide-arrows guide-liner-arrows" markerEnd={arrow}><path d="M126 188 C207 150 319 153 400 185" /><path d="M418 191 C437 188 450 182 463 173" /></g>
  </EyeCanvas>;
  if (kind === "blend") return <EyeCanvas kind={kind}>
    <path className="guide-soft-base" d="M91 207 C170 148 291 139 421 199 C375 161 312 133 235 137 C174 139 123 163 91 207 Z" />
    <path className="guide-blend-band" d="M132 165 C211 115 326 116 393 167" />
    <g className="guide-blend-loops" markerEnd={arrow}><path d="M184 151 C166 135 191 122 207 139 C218 152 199 163 184 151" /><path d="M274 132 C255 116 282 105 298 122 C309 136 289 146 274 132" /><path d="M350 149 C332 133 357 120 373 137 C384 150 365 161 350 149" /></g>
  </EyeCanvas>;
  return <EyeCanvas kind={kind}><></></EyeCanvas>;
}

/** Standard teaching schematic. It does not claim measured face coordinates. */
export function StepIllustration({ action, personalization }: { action?: MakeupAction; personalization?: PersonalizedAction }) {
  const kind = guideKindFor(action);
  const parameters = personalization?.personalizationSource === "backend-personalization"
    ? personalization.backendPersonalization?.personalized_parameters
    : undefined;
  return <figure className={`step-illustration step-illustration-${kind}`} data-guide-kind={kind}>
    <figcaption>{action?.name || "当前步骤"} · 操作示意</figcaption>
    <Guide kind={kind} parameters={parameters} />
    <p>{action?.motion}</p>
    <small>{guideNotes[kind]} {parameters && (kind === "liner" || kind === "lower") ? "方向与范围使用本次 Face Adaptation 参数。" : "标准教学示意 · 未使用未经校准的人脸坐标。"}</small>
  </figure>;
}
