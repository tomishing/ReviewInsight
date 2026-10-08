import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { format, formatDistanceToNow, subDays, subMonths } from "date-fns";
import { exportApi } from "../api/endpoints.js";
import { useSummaryStore } from "../store/summary.js";
import { useThemesStore } from "../store/themes.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import ThemePanel from "../components/ThemePanel.jsx";
import ChartCard from "../components/charts/ChartCard.jsx";
import RatingTrend from "../components/charts/RatingTrend.jsx";
import SentimentBar from "../components/charts/SentimentBar.jsx";
import SentimentByMonth from "../components/charts/SentimentByMonth.jsx";
import ThemeBars from "../components/charts/ThemeBars.jsx";
import { pct } from "../components/charts/theme.js";

const STORES = [
  { value: "", label: "All stores" },
  { value: "play", label: "Google Play" },
  { value: "appstore", label: "App Store" },
];
const PRESETS = [
  { value: "", label: "All time" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "12m", label: "Last 12 months" },
  { value: "custom", label: "Custom" },
];
const ymd = (d) => format(d, "yyyy-MM-dd");

// URL search params -> API filters { store, from, to }.
function useFilters() {
  const [params, setParams] = useSearchParams();
  const store = params.get("store") || "";
  const range = params.get("range") || "";
  const customFrom = params.get("from") || "";
  const customTo = params.get("to") || "";

  const filters = useMemo(() => {
    const today = new Date();
    let from = "";
    let to = "";
    if (range === "30d") from = ymd(subDays(today, 29));
    else if (range === "90d") from = ymd(subDays(today, 89));
    else if (range === "12m") from = ymd(subMonths(today, 12));
    else if (range === "custom") [from, to] = [customFrom, customTo];
    return { store, from, to };
  }, [store, range, customFrom, customTo]);

  const update = (changes) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) (v ? next.set(k, v) : next.delete(k));
    if (changes.range !== undefined && changes.range !== "custom") {
      next.delete("from");
      next.delete("to");
    }
    setParams(next, { replace: true });
  };

  const label = [
    STORES.find((s) => s.value === store)?.label,
    range === "custom"
      ? [customFrom || "start", customTo || "today"].join(" → ")
      : PRESETS.find((p) => p.value === range)?.label,
  ].join(" · ");

  return { filters, store, range, customFrom, customTo, update, label };
}

function Filters({ f }) {
  const select = "rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm";
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <select className={select} value={f.range} onChange={(e) => f.update({ range: e.target.value })} aria-label="Date range">
        {PRESETS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
      </select>
      {f.range === "custom" && (
        <>
          <input type="date" className={select} value={f.customFrom} max={f.customTo || undefined} onChange={(e) => f.update({ from: e.target.value })} aria-label="From" />
          <span className="text-sm text-slate-400">to</span>
          <input type="date" className={select} value={f.customTo} min={f.customFrom || undefined} onChange={(e) => f.update({ to: e.target.value })} aria-label="To" />
        </>
      )}
      <div className="inline-flex rounded-md border border-slate-300 bg-white p-0.5" role="group" aria-label="Store">
        {STORES.map((s) => (
          <button
            key={s.value}
            onClick={() => f.update({ store: s.value })}
            aria-pressed={f.store === s.value}
            className={`rounded px-2.5 py-1 text-sm ${f.store === s.value ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, note }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
      {note && <div className="mt-0.5 text-xs text-slate-500">{note}</div>}
    </div>
  );
}

export default function AppDetail() {
  const { id } = useParams();
  const appId = Number(id);
  const f = useFilters();
  const { data, loading, error, load, reset } = useSummaryStore();
  const openTheme = useThemesStore((s) => s.open);
  const closeTheme = useThemesStore((s) => s.close);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  const doExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      await exportApi.markdown(appId);
    } catch (e) {
      setExportError(e.message);
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    load(appId, f.filters);
  }, [appId, f.filters, load]);

  // Leaving the page (or switching app) drops the old app's data and closes the panel.
  useEffect(() => () => (reset(), closeTheme()), [appId, reset, closeTheme]);

  const reload = () => load(appId, f.filters);
  const current = data && data.app.id === appId ? data : null;

  if (!current) {
    return (
      <section>
        <Link to="/apps" className="text-sm text-slate-500 hover:underline">← Apps</Link>
        <div className="mt-6">
          {error ? (
            <ErrorState title="Couldn't load this app" message={error} onRetry={reload} />
          ) : (
            <div className="py-16"><LoadingSpinner label="Loading summary…" /></div>
          )}
        </div>
      </section>
    );
  }

  const { app, totals, sentiment, monthly, themes, generic } = current;
  const filtered = !!(f.filters.store || f.filters.from || f.filters.to);
  const analysedTotal = sentiment.positive + sentiment.neutral + sentiment.negative;
  const hasThemes = Object.values(themes).some((t) => t.length) || Object.values(generic).some(Boolean);

  let content;
  if (!totals.reviews) {
    content = filtered ? (
      <EmptyState title="No reviews match these filters">Try another date range or store.</EmptyState>
    ) : (
      <EmptyState title="No reviews yet" action={<Link to="/apps" className="text-sm font-medium text-slate-900 underline">Go to Apps</Link>}>
        Use <b>Fetch</b> on the Apps page to download {app.name}'s reviews, then <b>Analyse</b> them.
      </EmptyState>
    );
  } else {
    content = (
      <>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Reviews" value={totals.reviews.toLocaleString()} note={totals.first_review && `${format(new Date(totals.first_review), "MMM yyyy")} – ${format(new Date(totals.last_review), "MMM yyyy")}`} />
          <Stat label="Average rating" value={totals.avg_rating != null ? `${totals.avg_rating.toFixed(2)} ★` : "—"} />
          <Stat label="Analysed" value={`${pct(totals.analysed, totals.reviews)}%`} note={`${totals.analysed.toLocaleString()} of ${totals.reviews.toLocaleString()}`} />
          <Stat label="Negative" value={analysedTotal ? `${pct(sentiment.negative, analysedTotal)}%` : "—"} note="of analysed reviews" />
        </div>

        {totals.analysed < totals.reviews && (
          <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {(totals.reviews - totals.analysed).toLocaleString()} review{totals.reviews - totals.analysed === 1 ? " is" : "s are"} not analysed yet — run <b>Analyse</b> on the{" "}
            <Link to="/apps" className="underline">Apps page</Link> to include them.
          </p>
        )}

        <ChartCard title="Sentiment" subtitle="Analysed reviews in this selection" className="mt-4">
          <SentimentBar sentiment={sentiment} />
        </ChartCard>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <RatingTrend monthly={monthly} />
          <SentimentByMonth monthly={monthly} />
        </div>

        {hasThemes ? (
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            {[["pain", "Pain points"], ["positive", "Positive points"], ["request", "Feature requests"]].map(([key, title]) => (
              <ThemeBars
                key={key}
                title={title}
                themes={themes[key]}
                generic={generic[key]}
                totalReviews={totals.analysed}
                onSelect={(t) => openTheme(t.id, f.filters)}
              />
            ))}
          </div>
        ) : (
          <div className="mt-4">
            <EmptyState title={totals.analysed ? "No themes in this selection" : "No themes yet"}>
              {totals.analysed
                ? "None of the analysed reviews in this selection belong to a theme."
                : <>Run <b>Analyse</b> on the <Link to="/apps" className="underline">Apps page</Link> to extract pain points, positives and requests.</>}
            </EmptyState>
          </div>
        )}
      </>
    );
  }

  return (
    <section>
      <Link to="/apps" className="text-sm text-slate-500 hover:underline">← Apps</Link>
      <div className="mb-4 mt-1 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">{app.name}</h1>
          <p className="text-xs text-slate-500">
            {[app.play_id && `Play ${app.play_id}`, app.appstore_id && `App Store ${app.appstore_id}`].filter(Boolean).join(" · ")}
            {current.themes_updated_at && ` · themes updated ${formatDistanceToNow(new Date(current.themes_updated_at), { addSuffix: true })}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {loading && <LoadingSpinner size="sm" label="Updating…" />}
          <button
            onClick={doExport}
            disabled={exporting}
            title="Markdown report for the Obsidian vault (all reviews, no raw review text)"
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
          >
            {exporting ? "Exporting…" : "Export Markdown"}
          </button>
        </div>
      </div>
      {exportError && <div className="mb-4"><ErrorState title="Export failed" message={exportError} onRetry={doExport} /></div>}
      <Filters f={f} />
      {error && <div className="mb-4"><ErrorState title="Couldn't update the summary" message={error} onRetry={reload} /></div>}
      {/* Refetch keeps the previous render, dimmed, instead of flashing a spinner. */}
      <div className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>{content}</div>
      <ThemePanel filters={f.filters} filterLabel={filtered ? f.label : ""} />
    </section>
  );
}
