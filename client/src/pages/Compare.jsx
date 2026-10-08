import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { exportApi } from "../api/endpoints.js";
import { useCompareStore } from "../store/compare.js";
import { useThemesStore } from "../store/themes.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import ThemePanel from "../components/ThemePanel.jsx";

const TYPES = [
  { value: "pain", label: "Pain points" },
  { value: "positive", label: "Positive points" },
  { value: "request", label: "Feature requests" },
];

// Sequential blue ramp (one hue, more = darker) for share of an app's analysed reviews.
// Ink flips to white from the 4th step so cell text always clears contrast.
const RAMP = [
  { max: 0.01, bg: "#cde2fb", ink: "#0b0b0b", label: "< 1%" },
  { max: 0.025, bg: "#9ec5f4", ink: "#0b0b0b", label: "1–2.5%" },
  { max: 0.05, bg: "#6da7ec", ink: "#0b0b0b", label: "2.5–5%" },
  { max: 0.1, bg: "#2a78d6", ink: "#ffffff", label: "5–10%" },
  { max: Infinity, bg: "#1c5cab", ink: "#ffffff", label: "≥ 10%" },
];
const SMALL_SAMPLE = 30;
const step = (share) => RAMP.find((r) => share < r.max);

// 0.004 -> "0.4%", 0.25 -> "25%": small shares never round to "0%".
export const fmtShare = (x) => (x > 0 && x < 0.1 ? `${(x * 100).toFixed(1)}%` : `${Math.round(x * 100)}%`);

function Cell({ cell, onOpen }) {
  if (!cell) return <td className="border-l border-slate-100 px-2 py-2" />;
  const s = step(cell.share);
  const themes = cell.themes.map((t) => `${t.label} (${t.review_count})`).join("\n");
  return (
    <td className="border-l border-slate-100 p-1">
      <button
        onClick={onOpen}
        title={`${cell.review_count} reviews · ${fmtShare(cell.share)} of analysed\nThemes:\n${themes}\nClick to read the reviews`}
        className="w-full rounded px-2 py-1.5 text-right tabular-nums outline-offset-2 hover:ring-2 hover:ring-slate-900/30"
        style={{ background: s.bg, color: s.ink }}
      >
        <span className="font-semibold">{fmtShare(cell.share)}</span>
        <span className="ml-1 text-xs opacity-80">({cell.review_count})</span>
      </button>
    </td>
  );
}

export default function Compare() {
  const [params, setParams] = useSearchParams();
  const type = TYPES.some((t) => t.value === params.get("type")) ? params.get("type") : "pain";
  const onlyShared = params.get("shared") === "1";
  const { data, loading, error, refreshing, refreshError, load, refresh } = useCompareStore();
  const openGroup = useThemesStore((s) => s.openGroup);
  const closePanel = useThemesStore((s) => s.close);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  useEffect(() => {
    load(type);
  }, [type, load]);
  useEffect(() => closePanel, [closePanel]);

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    v ? next.set(k, v) : next.delete(k);
    setParams(next, { replace: true });
  };

  const doExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      await exportApi.markdown();
    } catch (e) {
      setExportError(e.message);
    } finally {
      setExporting(false);
    }
  };

  const current = data && data.type === type ? data : null;
  const shared = current ? current.groups.filter((g) => g.apps_count >= 2) : [];
  const rows = current ? (onlyShared ? shared : current.groups) : [];
  const typeLabel = TYPES.find((t) => t.value === type).label.toLowerCase();

  let body;
  if (!current) {
    body = error ? (
      <ErrorState title="Couldn't load the comparison" message={error} onRetry={() => load(type)} />
    ) : (
      <div className="py-16"><LoadingSpinner label="Loading comparison…" /></div>
    );
  } else if (current.apps.length < 2) {
    body = (
      <EmptyState title="Analyse at least two apps to compare them" action={<Link to="/apps" className="text-sm font-medium underline">Go to Apps</Link>}>
        {current.apps.length === 1 ? `Only ${current.apps[0].name} has ${typeLabel} so far.` : `No app has ${typeLabel} yet.`} Use <b>Fetch</b> and <b>Analyse</b> on the Apps page.
      </EmptyState>
    );
  } else if (!current.groups.length) {
    body = (
      <EmptyState
        title="No comparison built yet"
        action={
          <button onClick={() => refresh(type)} disabled={refreshing} className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
            {refreshing ? "Building…" : "Build comparison"}
          </button>
        }
      >
        Groups each app's {typeLabel} into shared topics with Claude (theme labels only — a fraction of a cent).
      </EmptyState>
    );
  } else {
    body = (
      <>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={onlyShared} onChange={(e) => setParam("shared", e.target.checked ? "1" : "")} />
            Only topics shared by 2+ apps ({shared.length})
          </label>
          <div className="flex items-center gap-1.5" aria-label="Colour scale">
            <span>Share of the app's analysed reviews:</span>
            {RAMP.map((r) => (
              <span key={r.label} className="flex items-center gap-1">
                <span className="h-3 w-4 rounded-sm" style={{ background: r.bg }} aria-hidden />
                {r.label}
              </span>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium uppercase tracking-wide">Topic</th>
                {current.apps.map((a) => (
                  <th key={a.id} className="border-l border-slate-100 px-2 py-2 text-right font-medium">
                    <Link to={`/apps/${a.id}`} className="text-slate-800 hover:underline">{a.name}</Link>
                    <div className="font-normal">
                      {a.analysed.toLocaleString()} analysed
                      {a.analysed < SMALL_SAMPLE && <span title="Few analysed reviews: shares are unreliable"> · small sample</span>}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((g) => (
                <tr key={g.id} className={`border-t border-slate-100 ${g.apps_count >= 2 ? "bg-amber-50/40" : ""}`}>
                  <td className={`px-4 py-2 align-top ${g.apps_count >= 2 ? "border-l-4 border-l-amber-400" : "border-l-4 border-l-transparent"}`}>
                    <div className="font-medium text-slate-900">{g.label}</div>
                    {g.description && <div className="text-xs text-slate-500">{g.description}</div>}
                    {g.apps_count >= 2 && (
                      <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                        <span aria-hidden>⚑</span> Shared by {g.apps_count} apps
                      </span>
                    )}
                  </td>
                  {current.apps.map((a) => (
                    <Cell key={a.id} cell={g.cells[String(a.id)]} onOpen={() => openGroup(g.id, a.id)} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <p className="p-4 text-sm text-slate-500">No topics are shared by two or more apps yet.</p>}
        </div>
      </>
    );
  }

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Compare</h1>
          <p className="text-sm text-slate-500">
            Topics across apps. {type === "pain" && "Pain points shared by several competitors are opportunities for PopNickel."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {current?.built_at && (
            <span className="text-xs text-slate-500">Built {formatDistanceToNow(new Date(current.built_at), { addSuffix: true })}</span>
          )}
          {current?.groups.length > 0 && (
            <button onClick={() => refresh(type)} disabled={refreshing} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50">
              {refreshing ? "Rebuilding…" : "Rebuild"}
            </button>
          )}
          <button onClick={doExport} disabled={exporting} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50">
            {exporting ? "Exporting…" : "Export Markdown"}
          </button>
        </div>
      </div>

      <div className="mb-4 inline-flex rounded-md border border-slate-300 bg-white p-0.5" role="tablist">
        {TYPES.map((t) => (
          <button
            key={t.value}
            role="tab"
            aria-selected={type === t.value}
            onClick={() => setParam("type", t.value === "pain" ? "" : t.value)}
            className={`rounded px-3 py-1 text-sm ${type === t.value ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {refreshing && <div className="mb-3"><LoadingSpinner size="sm" label="Grouping themes across apps with Claude…" /></div>}
      {refreshError && <div className="mb-3"><ErrorState title="Couldn't rebuild the comparison" message={refreshError} onRetry={() => refresh(type)} /></div>}
      {exportError && <div className="mb-3"><ErrorState title="Export failed" message={exportError} onRetry={doExport} /></div>}
      {current?.stale && current.groups.length > 0 && !refreshing && (
        <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {current.unmatched_themes} theme{current.unmatched_themes === 1 ? " has" : "s have"} changed since this comparison was built (an app was analysed again).{" "}
          <button onClick={() => refresh(type)} className="font-medium underline">Rebuild</button> to include them.
        </p>
      )}
      {error && current && <div className="mb-3"><ErrorState title="Couldn't update the comparison" message={error} onRetry={() => load(type)} /></div>}

      <div className={loading && current ? "opacity-60 transition-opacity" : "transition-opacity"}>{body}</div>
      <ThemePanel />
    </section>
  );
}
