import { SENTIMENT, pct } from "./theme.js";

// Part-to-whole as one horizontal stacked bar (positive → neutral → negative) with a legend
// that carries counts and shares in text.
export default function SentimentBar({ sentiment }) {
  const total = SENTIMENT.reduce((s, x) => s + (sentiment[x.key] || 0), 0);
  if (!total) return <p className="text-sm text-slate-500">No analysed reviews in this selection.</p>;
  const parts = SENTIMENT.filter((x) => sentiment[x.key] > 0);
  return (
    <div>
      <div className="flex h-6 w-full gap-[2px]" role="img" aria-label={SENTIMENT.map((x) => `${x.label} ${pct(sentiment[x.key], total)}%`).join(", ")}>
        {parts.map((x, i) => (
          <div
            key={x.key}
            title={`${x.label}: ${sentiment[x.key]} (${pct(sentiment[x.key], total)}%)`}
            style={{ width: `${(sentiment[x.key] / total) * 100}%`, background: x.color }}
            className={`${i === 0 ? "rounded-l" : ""} ${i === parts.length - 1 ? "rounded-r" : ""} min-w-[3px]`}
          />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {SENTIMENT.map((x) => (
          <li key={x.key} className="flex items-center gap-1.5 text-slate-700">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: x.color }} aria-hidden />
            {x.label}
            <span className="font-semibold text-slate-900">{pct(sentiment[x.key], total)}%</span>
            <span className="text-xs text-slate-500">({sentiment[x.key].toLocaleString()})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
