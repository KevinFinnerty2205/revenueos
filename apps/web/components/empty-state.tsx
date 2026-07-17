interface EmptyStateProps {
  eyebrow?: string;
  title: string;
  description: string;
}

export function EmptyState({
  eyebrow = "Not configured",
  title,
  description,
}: EmptyStateProps) {
  return (
    <section
      className="rounded-3xl border border-dashed border-slate-300 bg-white/70 p-8 shadow-sm sm:p-12"
      aria-labelledby="empty-state-title"
    >
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700">
        {eyebrow}
      </p>
      <h2
        id="empty-state-title"
        className="mt-3 max-w-xl text-2xl font-semibold tracking-tight text-slate-950"
      >
        {title}
      </h2>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
        {description}
      </p>
    </section>
  );
}
