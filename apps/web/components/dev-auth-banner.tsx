export function DevAuthBanner() {
  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs font-semibold tracking-wide text-amber-900">
      Development mode: mock authentication is active. No Clerk account is
      connected.
    </div>
  );
}
