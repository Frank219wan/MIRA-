export function StepNavigator({
  index,
  count,
  onChange,
}: {
  index: number;
  count: number;
  onChange: (i: number) => void;
}) {
  return (
    <nav className="step-nav" aria-label="教程步骤">
      {Array.from({ length: count }, (_, i) => (
        <button
          key={i}
          aria-label={`第 ${i + 1} 步`}
          aria-current={i === index ? "step" : undefined}
          className={i === index ? "active" : ""}
          onClick={() => onChange(i)}
        >
          <span>0{i + 1}</span>
          <span>{i === index ? "当前步骤" : "步骤"}</span>
        </button>
      ))}
    </nav>
  );
}
