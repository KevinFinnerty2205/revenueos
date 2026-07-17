export default function ProtectedLoading() {
  return (
    <div role="status" aria-live="polite" className="space-y-6">
      <span className="sr-only">Loading workspace</span>
      <div className="h-4 w-32 animate-pulse rounded-full bg-slate-200 motion-reduce:animate-none" />
      <div className="h-12 max-w-xl animate-pulse rounded-2xl bg-slate-200 motion-reduce:animate-none" />
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="h-40 animate-pulse rounded-3xl bg-white motion-reduce:animate-none" />
        <div className="h-40 animate-pulse rounded-3xl bg-white motion-reduce:animate-none" />
      </div>
    </div>
  );
}
