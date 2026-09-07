import type { Severity } from "@/types/api";
import clsx from "clsx";

const SEVERITY_STYLES: Record<Severity, string> = {
  LOW: "text-severity-low border-severity-low/40 bg-severity-low/10",
  MODERATE: "text-severity-moderate border-severity-moderate/40 bg-severity-moderate/10",
  HIGH: "text-severity-high border-severity-high/40 bg-severity-high/10",
  CRITICAL: "text-severity-critical border-severity-critical/40 bg-severity-critical/10",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center border px-2 py-0.5 text-xs font-medium tabular",
        SEVERITY_STYLES[severity]
      )}
    >
      {severity}
    </span>
  );
}

export function severityColor(severity: Severity): string {
  switch (severity) {
    case "LOW":
      return "var(--severity-low)";
    case "MODERATE":
      return "var(--severity-moderate)";
    case "HIGH":
      return "var(--severity-high)";
    case "CRITICAL":
      return "var(--severity-critical)";
  }
}
