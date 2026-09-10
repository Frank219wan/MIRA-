/** Format service-provided capability text without inventing product properties or colors. */
export function CapabilityTags({ value }: { value: string }) {
  return (
    <span className="capability-tags">
      {value.split("·").map((part, i) => (
        <span key={`${i}-${part}`}>{part.trim()}</span>
      ))}
    </span>
  );
}
