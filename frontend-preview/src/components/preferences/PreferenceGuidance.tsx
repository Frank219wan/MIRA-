import type { LocalAppearanceGuidance } from "../../services/localAppearance";
export function PreferenceGuidance({
  guidance,
  actionId,
}: {
  guidance: LocalAppearanceGuidance[];
  actionId?: string;
}) {
  const items = actionId
    ? guidance.filter(
        (g) => !g.actionIds.length || g.actionIds.includes(actionId),
      )
    : guidance;
  if (!items.length) return null;
  return (
    <details className="coach-context preference-guidance">
      <summary>局部呈现偏好 · {items.length} 个区域</summary>
      <p className="face-scan-note">根据你的选择提供的上妆建议。</p>
      {items.map((g) => (
        <section key={g.region}>
          <h3>
            {g.region} · {g.label}
            {g.integrateStyle &&
              ` · ${g.integrateStyle === "natural" ? "自然保留" : "突出呈现"}`}
          </h3>
          <p>{g.instruction}</p>
          <p>做到这里就可以：{g.stopWhen}</p>
          {!g.actionIds.length && (
            <small>本教程未包含该区域的底妆步骤，可在需要时参考。</small>
          )}
        </section>
      ))}
    </details>
  );
}
