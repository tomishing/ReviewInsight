import { useState } from "react";

// Card with a title and an optional "Table" toggle so every chart has a table view.
export default function ChartCard({ title, subtitle, table, children, className = "" }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-4 ${className}`}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>
        {table && (
          <button
            onClick={() => setShowTable(!showTable)}
            className="shrink-0 rounded px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-100"
            aria-pressed={showTable}
          >
            {showTable ? "Chart" : "Table"}
          </button>
        )}
      </div>
      {showTable ? <div className="max-h-80 overflow-auto">{table}</div> : children}
    </div>
  );
}

export function DataTable({ columns, rows }) {
  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-white text-left text-slate-500">
        <tr>{columns.map((c) => <th key={c.key} className={`py-1 pr-3 font-medium ${c.right ? "text-right" : ""}`}>{c.label}</th>)}</tr>
      </thead>
      <tbody className="tabular-nums text-slate-700">
        {rows.map((r, i) => (
          <tr key={i} className="border-t border-slate-100">
            {columns.map((c) => <td key={c.key} className={`py-1 pr-3 ${c.right ? "text-right" : ""}`}>{c.format ? c.format(r[c.key], r) : r[c.key]}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
