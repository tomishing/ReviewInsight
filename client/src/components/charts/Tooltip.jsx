// Shared tooltip shell: value first (strong), label secondary.
export function TooltipBox({ title, rows }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium text-slate-500">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2">
          {r.color && <span className="h-0.5 w-3 rounded" style={{ background: r.color }} aria-hidden />}
          <span className="font-semibold tabular-nums text-slate-900">{r.value}</span>
          <span className="text-slate-500">{r.label}</span>
        </div>
      ))}
    </div>
  );
}
