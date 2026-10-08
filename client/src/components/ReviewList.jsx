import { format } from "date-fns";
import { SENTIMENT } from "./charts/theme.js";

const SENT = Object.fromEntries(SENTIMENT.map((s) => [s.key, s]));

function Stars({ n }) {
  if (!n) return null;
  return (
    <span className="tracking-tight text-amber-500" aria-label={`${n} out of 5 stars`}>
      {"★".repeat(n)}<span className="text-slate-300">{"★".repeat(5 - n)}</span>
    </span>
  );
}

// Original reviews: rating, store, date, version, sentiment, text and extracted phrases.
export default function ReviewList({ reviews }) {
  return (
    <ul className="space-y-4">
      {reviews.map((r) => (
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
  );
}
