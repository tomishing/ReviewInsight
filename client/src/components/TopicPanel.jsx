import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { format } from "date-fns";
import { compareApi } from "../api/endpoints.js";
import { useCompareStore } from "../store/compare.js";
import ErrorState from "./ErrorState.jsx";
import LoadingSpinner from "./LoadingSpinner.jsx";
import ReviewList from "./ReviewList.jsx";
import SentimentBar from "./charts/SentimentBar.jsx";

const TYPE = { pain: "Pain point", positive: "Positive point", request: "Feature request" };
const fmtShare = (x) => (x > 0 && x < 0.1 ? `${(x * 100).toFixed(1)}%` : `${Math.round(x * 100)}%`);
const day = (iso) => (iso ? format(new Date(iso), "d MMM yyyy") : "—");

// Reviews behind one app's part of the topic, loaded on demand.
function AppReviews({ groupId, appId, count }) {
  const [state, setState] = useState({ open: false, data: null, loading: false, error: null });
  const load = async () => {
    setState((s) => ({ ...s, open: true, loading: true, error: null }));
    try {
      const data = await compareApi.groupReviews(groupId, appId);
      setState({ open: true, data, loading: false, error: null });
    } catch (e) {
      setState({ open: true, data: null, loading: false, error: e.message });
    }
  };
  const toggle = () => (state.open ? setState((s) => ({ ...s, open: false })) : state.data ? setState((s) => ({ ...s, open: true })) : load());
  return (
    <div className="mt-3">
      <button onClick={toggle} className="text-sm font-medium text-slate-700 underline-offset-2 hover:underline" aria-expanded={state.open}>
        {state.open ? "Hide reviews" : `Show ${count} review${count === 1 ? "" : "s"}`}
      </button>
      {state.open && (
        <div className="mt-2">
          {state.loading && <LoadingSpinner size="sm" label="Loading reviews…" />}
          {state.error && <ErrorState title="Couldn't load reviews" message={state.error} onRetry={load} />}
          {state.data && <ReviewList reviews={state.data.reviews} />}
        </div>
      )}
    </div>
  );
}

function RatingCompare({ topic, overall }) {
  if (topic == null) return <span>—</span>;
  const diff = overall != null ? topic - overall : null;
  return (
    <span>
      <span className="font-semibold text-slate-900">{topic.toFixed(2)} ★</span>
      {diff != null && (
        <span className="ml-1 text-xs text-slate-500">
          vs {overall.toFixed(2)} overall ({diff >= 0 ? "+" : "−"}{Math.abs(diff).toFixed(2)})
        </span>
      )}
    </span>
  );
}

// Side panel: one comparison topic summarised per app.
export default function TopicPanel() {
  const { topicId, topic, topicLoading, topicError, openTopic, closeTopic } = useCompareStore();

  useEffect(() => {
    if (!topicId) return;
    const onKey = (e) => e.key === "Escape" && closeTopic();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [topicId, closeTopic]);

  if (!topicId) return null;
  const g = topic?.group;
  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-slate-900/20" onMouseDown={closeTopic}>
      <aside className="flex h-full w-full max-w-2xl flex-col bg-white shadow-xl" onMouseDown={(e) => e.stopPropagation()} aria-label="Topic summary">
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 p-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{g ? `${TYPE[g.type]} · topic` : "Topic"}</p>
            <h2 className="mt-0.5 text-lg font-semibold">{g?.label ?? "…"}</h2>
            {g?.description && <p className="mt-1 text-sm text-slate-600">{g.description}</p>}
            {topic && (
              <p className="mt-1 text-xs text-slate-500">
                {topic.review_count} review{topic.review_count === 1 ? "" : "s"} across {topic.apps_count} app{topic.apps_count === 1 ? "" : "s"}
              </p>
            )}
          </div>
          <button onClick={closeTopic} className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100" aria-label="Close">✕</button>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto bg-slate-50 p-4">
          {topicLoading && <div className="py-12"><LoadingSpinner label="Loading topic…" /></div>}
          {topicError && <ErrorState title="Couldn't load this topic" message={topicError} onRetry={() => openTopic(topicId)} />}
          {topic?.apps.map((a) => (
            <section key={a.app_id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-baseline justify-between gap-2">
                <Link to={`/apps/${a.app_id}`} className="font-semibold text-slate-900 hover:underline">{a.name}</Link>
                <span className="text-sm">
                  <span className="font-semibold text-slate-900">{fmtShare(a.share)}</span>
                  <span className="text-slate-500"> of {a.app_analysed.toLocaleString()} analysed · {a.review_count} review{a.review_count === 1 ? "" : "s"}</span>
                </span>
              </div>
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                <dt className="text-slate-500">Rating</dt>
                <dd><RatingCompare topic={a.avg_rating} overall={a.app_avg_rating} /></dd>
                <dt className="text-slate-500">Mentioned</dt>
                <dd className="text-slate-700">{day(a.first_review)} – {day(a.last_review)}</dd>
              </dl>
              <div className="mt-3"><SentimentBar sentiment={a.sentiment} /></div>
              <div className="mt-3 space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {a.themes.length === 1 ? "Theme" : `${a.themes.length} themes`} in {a.name}
                </p>
                {a.themes.map((t) => (
                  <div key={t.id} className="text-sm">
                    <span className="font-medium text-slate-900">{t.label}</span>
                    <span className="text-xs text-slate-500"> · {t.review_count} review{t.review_count === 1 ? "" : "s"}</span>
                    {t.description && <p className="text-slate-600">{t.description}</p>}
                    {t.example_phrases?.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {t.example_phrases.map((p, i) => <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">“{p}”</span>)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <AppReviews groupId={topicId} appId={a.app_id} count={a.review_count} />
            </section>
          ))}
        </div>
      </aside>
    </div>
  );
}
