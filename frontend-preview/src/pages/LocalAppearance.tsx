import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Page } from "../components/layout/Page";
import { Button } from "../components/ui/button";
import {
  regions,
  preferenceOptions,
  getLocalAppearancePreferences,
  setLocalAppearancePreferences,
  clearLocalAppearancePreferences,
  type LocalRegion,
  type AppearancePreference,
  type LocalAppearancePreference,
} from "../services/localAppearance";
import { hasFaceProfile } from "../services/face";
export default function LocalAppearance() {
  const nav = useNavigate();
  const [values, setValues] = useState(getLocalAppearancePreferences);
  const [region, setRegion] = useState<LocalRegion>();
  const [preference, setPreference] = useState<AppearancePreference>();
  const [style, setStyle] = useState<"natural" | "highlight" | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const marker = region
    ? (
        {
          额头: [100, 52, 32, 15],
          左脸颊: [130, 120, 18, 23],
          右脸颊: [70, 120, 18, 23],
          鼻部: [100, 108, 12, 22],
          下巴: [100, 158, 22, 12],
          眼周: [100, 83, 40, 16],
        } as const
      )[region]
    : null;
  const ready = region && preference && (preference !== "integrate" || style);
  function save() {
    if (!ready) return;
    const next = [
      ...values.filter((v) => v.region !== region),
      {
        region,
        preference,
        integrateStyle: preference === "integrate" ? style : null,
      } as LocalAppearancePreference,
    ];
    try {
      setLocalAppearancePreferences(next);
      setValues(next);
      setSaved(true);
      setError("");
    } catch {
      setError("未能保存偏好，请检查浏览器存储后重试。");
    }
  }
  return (
    <Page
      eyebrow="03 / 适配面部"
      title={saved ? "偏好已加入本次教程" : "这里想怎么呈现？"}
      description={
        saved
          ? "已保存你的选择，将作为本次教程的局部上妆提示。"
          : "手动选择一个区域，设置今天希望的呈现方式；无需上传照片。"
      }
      backTo={hasFaceProfile() ? "/beauty-profile" : "/face-scan"}
      progress={75}
    >
      {saved ? (
        <>
          <dl className="preference-summary">
            {values.map((v) => (
              <div key={v.region}>
                <dt>{v.region}</dt>
                <dd>
                  {preferenceOptions.find((o) => o[0] === v.preference)?.[1]}
                  {v.integrateStyle &&
                    ` · ${v.integrateStyle === "natural" ? "自然保留" : "突出呈现"}`}
                </dd>
              </div>
            ))}
          </dl>
          <p>
            对应区域有底妆步骤时会加入提示；其他区域可在教程中查看单独建议。
          </p>
          <div className="action-row">
            <Button
              variant="outline"
              onClick={() => {
                setSaved(false);
                setRegion(undefined);
                setPreference(undefined);
                setStyle(null);
              }}
            >
              设置其他区域
            </Button>
            <Button asChild>
              <Link to="/my-tutorial">继续生成我的教程 →</Link>
            </Button>
          </div>
        </>
      ) : (
        <>
          {marker && (
            <figure className="preference-region-map">
              <svg
                viewBox="0 0 200 200"
                role="img"
                aria-label={`${region}位置示意，以你自身的左右为准`}
              >
                <path
                  d="M100 20 C55 20 43 52 48 94 C51 143 76 180 100 180 C124 180 149 143 152 94 C157 52 145 20 100 20Z"
                  fill="none"
                  stroke="#D5D5D5"
                  strokeWidth="1.2"
                />
                <ellipse
                  cx={marker[0]}
                  cy={marker[1]}
                  rx={marker[2]}
                  ry={marker[3]}
                  fill="#E8E8E8"
                  fillOpacity=".5"
                  stroke="#999"
                  strokeWidth=".8"
                />
              </svg>
              <figcaption>{region} · 位置示意，以你自身的左右为准</figcaption>
            </figure>
          )}
          <fieldset className="preference-regions">
            <legend>选择区域</legend>
            {regions.map((r) => (
              <label key={r}>
                <input
                  type="radio"
                  name="region"
                  checked={region === r}
                  onChange={() => {
                    setRegion(r);
                    const old = values.find((v) => v.region === r);
                    setPreference(old?.preference);
                    setStyle(old?.integrateStyle ?? null);
                  }}
                />
                <span>{r}</span>
              </label>
            ))}
          </fieldset>
          <fieldset className="preference-options">
            <legend>局部呈现偏好</legend>
            {preferenceOptions.map(([id, label, description]) => (
              <label key={id}>
                <input
                  type="radio"
                  name="preference"
                  checked={preference === id}
                  onChange={() => {
                    setPreference(id);
                    setStyle(null);
                  }}
                />
                <span>
                  <strong>{label}</strong>
                  <small>{description}</small>
                </span>
              </label>
            ))}
          </fieldset>
          {preference === "integrate" && (
            <fieldset className="preference-options">
              <legend>你希望怎样融入这次妆容？</legend>
              {(
                [
                  [
                    "natural",
                    "自然保留",
                    "保持原有视觉特征，让其他妆容围绕它调整。",
                  ],
                  [
                    "highlight",
                    "突出呈现",
                    "参考教程的色彩与光泽，让周围妆容呼应这个区域。",
                  ],
                ] as const
              ).map(([id, label, description]) => (
                <label key={id}>
                  <input
                    type="radio"
                    name="integrate"
                    checked={style === id}
                    onChange={() => setStyle(id)}
                  />
                  <span>
                    <strong>{label}</strong>
                    <small>{description}</small>
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          <div className="action-row">
            <Button disabled={!ready} onClick={save}>
              加入本次教程
            </Button>
            <Button
              variant="tertiary"
              onClick={() => {
                try {
                  clearLocalAppearancePreferences();
                  nav("/my-tutorial");
                } catch {
                  setError("未能清除偏好，请重试。");
                }
              }}
            >
              今天不设置
            </Button>
          </div>
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </Page>
  );
}
