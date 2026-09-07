import clsx from "clsx";
import { AlertCircle } from "lucide-react";

export function Panel({
  title,
  action,
  children,
  className,
}: {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("border border-border bg-panel", className)}>
      {title && (
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-medium text-text">{title}</h2>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between">
      <div>
        <h1 className="text-xl font-semibold text-text">{title}</h1>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-text-muted">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Loading data" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-text-muted">
      <span className="h-1.5 w-1.5 animate-pulse bg-accent" />
      {label}...
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 border border-severity-critical/40 bg-severity-critical/10 px-4 py-3 text-sm text-severity-critical">
      <AlertCircle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="py-10 text-center text-sm text-text-muted">{message}</div>
  );
}
