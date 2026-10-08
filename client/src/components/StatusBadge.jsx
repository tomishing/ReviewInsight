// Run status with an icon + label, so state never relies on color alone.
const STYLES = {
  ok: ["✓", "bg-green-50 text-green-800 ring-green-200"],
  partial: ["!", "bg-amber-50 text-amber-800 ring-amber-200"],
  error: ["✕", "bg-red-50 text-red-800 ring-red-200"],
  running: ["…", "bg-slate-100 text-slate-700 ring-slate-200"],
};

export default function StatusBadge({ status, title }) {
  const [icon, cls] = STYLES[status] || STYLES.running;
  return (
    <span
      title={title || undefined}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}
    >
      <span aria-hidden>{icon}</span>
      {status}
    </span>
  );
}
