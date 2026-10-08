import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard, { DataTable } from "./ChartCard.jsx";
import { TooltipBox } from "./Tooltip.jsx";
import { fillMonths, monthLabel, monthLong } from "./months.js";
import { AXIS, GRID, MUTED, SENTIMENT, SURFACE, pct } from "./theme.js";

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  return (
    <TooltipBox
      title={`${monthLong(m.month)} · ${m.analysed} analysed`}
      rows={SENTIMENT.map((s) => ({ label: s.label.toLowerCase(), value: `${pct(m[s.key], m.analysed)}% (${m[s.key]})`, color: s.color }))}
    />
  );
}

// 100% stacked columns: share of positive / neutral / negative among analysed reviews per month.
export default function SentimentByMonth({ monthly }) {
  const data = fillMonths(monthly).map((m) => ({
    ...m,
    ...Object.fromEntries(SENTIMENT.map((s) => [`${s.key}_pct`, m.analysed ? (m[s.key] / m.analysed) * 100 : 0])),
  }));
  const table = (
    <DataTable
      columns={[
        { key: "month", label: "Month", format: monthLong },
        { key: "analysed", label: "Analysed", right: true },
        ...SENTIMENT.map((s) => ({ key: s.key, label: s.label, right: true, format: (v, r) => `${pct(v, r.analysed)}% (${v})` })),
      ]}
      rows={[...data].reverse()}
    />
  );
  return (
    <ChartCard title="Sentiment by month" subtitle="Share of analysed reviews" table={table}>
      {data.some((m) => m.analysed) ? (
        <>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }} barCategoryGap="20%">
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 11, fill: MUTED }} axisLine={{ stroke: AXIS }} tickLine={false} minTickGap={24} />
              <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: MUTED }} axisLine={false} tickLine={false} />
              <Tooltip content={<Tip />} cursor={{ fill: "rgba(11,11,11,0.04)" }} />
              {SENTIMENT.map((s, i) => (
                <Bar
                  key={s.key}
                  dataKey={`${s.key}_pct`}
                  stackId="s"
                  fill={s.color}
                  stroke={SURFACE}
                  strokeWidth={1}
                  maxBarSize={24}
                  radius={i === SENTIMENT.length - 1 ? [4, 4, 0, 0] : 0}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <ul className="mt-2 flex gap-4 text-xs text-slate-600">
            {SENTIMENT.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} aria-hidden />
                {s.label}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="text-sm text-slate-500">No analysed reviews in this selection.</p>
      )}
    </ChartCard>
  );
}
