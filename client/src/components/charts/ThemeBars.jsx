import { useState } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard, { DataTable } from "./ChartCard.jsx";
import { INK_2, SERIES, SERIES_HOVER, pct } from "./theme.js";

const TOP = 10;
const ROW = 30;
const LABEL_W = 190;
// ~6.6px per character at 12px: keep labels inside the label column instead of past its left edge.
const MAX_CHARS = Math.floor((LABEL_W - 12) / 6.6);

const truncate = (s, n = MAX_CHARS) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

function Tip({ active, payload, total }) {
  if (!active || !payload?.length) return null;
  const t = payload[0].payload;
  return (
    <div className="max-w-xs rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="flex items-baseline gap-1.5">
        <span className="font-semibold tabular-nums text-slate-900">{t.review_count}</span>
        <span className="text-slate-500">reviews · {pct(t.review_count, total)}%</span>
      </div>
      <div className="mt-1 font-medium text-slate-800">{t.label}</div>
      {t.description && <div className="mt-0.5 text-slate-600">{t.description}</div>}
      {t.example_phrases?.length > 0 && (
        <div className="mt-1 text-slate-500">e.g. {t.example_phrases.map((p) => `“${p}”`).join(", ")}</div>
      )}
      <div className="mt-1 text-slate-400">Click to read the reviews</div>
    </div>
  );
}

// Tick that truncates long theme labels and keeps the full label as a native tooltip.
function LabelTick({ x, y, payload, onClick }) {
  return (
    <text x={x - 6} y={y} dy={4} textAnchor="end" fontSize={12} fill={INK_2} style={{ cursor: "pointer" }} onClick={() => onClick(payload.index)}>
      <title>{payload.value}</title>
      {truncate(payload.value)}
    </text>
  );
}

export default function ThemeBars({ title, themes, generic, totalReviews, onSelect }) {
  const [hover, setHover] = useState(null);
  const data = themes.slice(0, TOP);
  const table = (
    <DataTable
      columns={[
        { key: "label", label: "Theme" },
        { key: "review_count", label: "Reviews", right: true },
        { key: "share", label: "Share", right: true, format: (_, r) => `${pct(r.review_count, totalReviews)}%` },
      ]}
      rows={themes}
    />
  );
  return (
    <ChartCard
      title={title}
      subtitle={themes.length > TOP ? `Top ${TOP} of ${themes.length} themes, by reviews` : "Themes by number of reviews"}
      table={themes.length ? table : null}
    >
      {data.length ? (
        <ResponsiveContainer width="100%" height={data.length * ROW + 8}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }} barCategoryGap={6}>
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis
              type="category"
              dataKey="label"
              width={LABEL_W}
              axisLine={false}
              tickLine={false}
              interval={0}
              tick={<LabelTick onClick={(i) => onSelect(data[i])} />}
            />
            <Tooltip content={<Tip total={totalReviews} />} cursor={{ fill: "rgba(11,11,11,0.04)" }} />
            <Bar
              dataKey="review_count"
              maxBarSize={18}
              radius={[0, 4, 4, 0]}
              style={{ cursor: "pointer" }}
              onClick={(d) => onSelect(d.payload ?? d)}
              onMouseEnter={(_, i) => setHover(i)}
              onMouseLeave={() => setHover(null)}
              isAnimationActive={false}
            >
              {data.map((t, i) => <Cell key={t.id} fill={i === hover ? SERIES_HOVER : SERIES} />)}
              <LabelList dataKey="review_count" position="right" fontSize={11} fill={INK_2} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-sm text-slate-500">No themes in this selection.</p>
      )}
      {generic > 0 && (
        <p className="mt-2 text-xs text-slate-500">
          Not ranked: {generic} review{generic === 1 ? "" : "s"} with only generic remarks (e.g. “great app”).
        </p>
      )}
    </ChartCard>
  );
}
