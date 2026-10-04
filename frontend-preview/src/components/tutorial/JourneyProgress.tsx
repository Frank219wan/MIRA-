export function JourneyProgress({ value }: { value: number }) {
  const progress = Math.min(100, Math.max(0, value));

  return (
    <div
      className="journey-progress"
      role="progressbar"
      aria-label="教程准备进度"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={progress}
    >
      <span style={{ width: `${progress}%` }} />
    </div>
  );
}
