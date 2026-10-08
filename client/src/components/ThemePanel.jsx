import { useEffect } from "react";
import { format } from "date-fns";
import { useThemesStore } from "../store/themes.js";
import ErrorState from "./ErrorState.jsx";
import LoadingSpinner from "./LoadingSpinner.jsx";
import { SENTIMENT } from "./charts/theme.js";

const SENT = Object.fromEntries(SENTIMENT.map((s) => [s.key, s]));
const TYPE = { pain: "Pain point", positive: "Positive point", request: "Feature request" };

function Stars({ n }) {
  if (!n) return null;
  return (
    <span className="tracking-tight text-amber-500" aria-label={`${n} out of 5 stars`}>
      {"★".repeat(n)}<span className="text-slate-300">{"★".repeat(5 - n)}</span>
    </span>
  );
}

// Side panel with the original reviews behind a theme.
export default function ThemePanel({ filters, filterLabel }) {
  const { openId, data, loading, error, retry, close } = useThemesStore();

  useEffect(() => {
    if (!openId) return;
    const onKey = (e) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openId, close]);

  if (!openId) return null;
  const theme = data?.theme;
  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-slate-900/20" onMouseDown={close}>
      <aside
        className="flex h-full w-full max-w-xl flex-col bg-white shadow-xl"
        onMouseDown={(e) => e.stopPropagation()}
        aria-label="Reviews behind theme"
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 p-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{theme ? TYPE[theme.type] : "Theme"}</p>
            <h2 className="mt-0.5 text-lg font-semibold">{theme?.label ?? "…"}</h2>
            {theme?.description && <p className="mt-1 text-sm text-slate-600">{theme.description}</p>}
            {data && (
              <p className="mt-1 text-xs text-slate-500">
                {data.reviews.length} review{data.reviews.length === 1 ? "" : "s"}{filterLabel ? ` · ${filterLabel}` : ""}
              </p>
            )}
          </div>
          <button onClick={close} className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100" aria-label="Close">✕</button>
        </header>
        <div className="flex-1 overflow-y-auto p-4">
          {loading && <div className="py-12"><LoadingSpinner label="Loading reviews…" /></div>}
          {error && <ErrorState title="Couldn't load reviews" message={error} onRetry={() => retry(filters)} />}
          {data && !data.reviews.length && <p className="text-sm text-slate-500">No reviews for this theme in the current selection.</p>}
          <ul className="space-y-4">
            {data?.reviews.map((r) => (
              <li key={r.id} className="rounded-md border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                  <Stars n={r.rating} />
                  <span>{r.store === "play" ? "Google Play" : "App Store"}</span>
                  {r.review_date && <span>{format(new Date(r.review_date), "d MMM yyyy")}</span>}
                  {r.app_version && <span>v{r.app_version}</span>}
                  {r.sentiment && (
                    <span className="inline-flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full" style={{ background: SENT[r.sentiment].color }} aria-hidden />
                      {SENT[r.sentiment].label}
                    </span>
                  )}
                </div>
                {r.title && <p className="mt-1.5 font-medium text-slate-900">{r.title}</p>}
                <p className="mt-1 whitespace-pre-line text-slate-700">{r.body}</p>
                {r.phrases?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {r.phrases.map((p, i) => (
                      <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{p}</span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
