export function StatReadout({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: "critical" | "high" | "default";
}) {
  const valueColor =
    accent === "critical"
      ? "text-severity-critical"
      : accent === "high"
      ? "text-severity-high"
      : "text-text";

  return (
    <div className="border border-border px-5 py-4">
      <div className="text-xs text-text-muted">{label}</div>
      <div className={`mt-1 text-3xl font-semibold tabular ${valueColor}`}>
        {value}
      </div>
    </div>
  );
}
