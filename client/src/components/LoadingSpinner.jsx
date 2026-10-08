export default function LoadingSpinner({ label = "Loading…", size = "md" }) {
  const dim = size === "sm" ? "h-4 w-4 border-2" : "h-8 w-8 border-[3px]";
  return (
    <div role="status" className="flex items-center justify-center gap-3 text-sm text-slate-500">
      <span className={`${dim} animate-spin rounded-full border-slate-300 border-t-slate-700`} />
      {label && <span>{label}</span>}
    </div>
  );
}
