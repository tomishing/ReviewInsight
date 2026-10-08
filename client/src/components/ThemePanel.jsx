import { useEffect } from "react";
import { useThemesStore } from "../store/themes.js";
import ErrorState from "./ErrorState.jsx";
import LoadingSpinner from "./LoadingSpinner.jsx";
import ReviewList from "./ReviewList.jsx";

const TYPE = { pain: "Pain point", positive: "Positive point", request: "Feature request" };

// Side panel with the original reviews behind a theme.
export default function ThemePanel({ filterLabel }) {
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
          {error && <ErrorState title="Couldn't load reviews" message={error} onRetry={retry} />}
          {data && !data.reviews.length && <p className="text-sm text-slate-500">No reviews for this theme in the current selection.</p>}
          {data && <ReviewList reviews={data.reviews} />}
        </div>
      </aside>
    </div>
  );
}
