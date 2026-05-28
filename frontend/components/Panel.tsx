export default function Panel({
  heading,
  children,
  className,
  actions,
}: {
  heading?: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
}) {
  return (
    <section className={`panel ${className ?? ""}`}>
      {(heading || actions) && (
        <header className="mb-3 flex items-center justify-between gap-2">
          {heading && <div className="panel-h">{heading}</div>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
