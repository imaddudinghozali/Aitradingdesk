export default function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="rounded border border-dashed border-shadow-border bg-shadow-bg/40 p-6 text-center">
      <div className="text-sm text-shadow-ink">{title}</div>
      {description && (
        <p className="mt-1 text-xs text-shadow-muted">{description}</p>
      )}
    </div>
  );
}
