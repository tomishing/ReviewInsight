import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard, { DataTable } from "./ChartCard.jsx";
import { TooltipBox } from "./Tooltip.jsx";
import { fillMonths, monthLabel, monthLong } from "./months.js";
import { AXIS, GRID, MUTED, SERIES, SURFACE } from "./theme.js";

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  return (
    <TooltipBox
      title={monthLong(m.month)}
      rows={[
        { label: "avg rating", value: m.avg_rating != null ? `${m.avg_rating.toFixed(2)} ★` : "—", color: SERIES },
        { label: "reviews", value: m.reviews.toLocaleString() },
      ]}
    />
  );
}

export default function RatingTrend({ monthly }) {
  const data = fillMonths(monthly);
  const table = (
    <DataTable
      columns={[
        { key: "month", label: "Month", format: monthLong },
        { key: "reviews", label: "Reviews", right: true },
        { key: "avg_rating", label: "Avg ★", right: true, format: (v) => (v == null ? "—" : v.toFixed(2)) },
      ]}
      rows={[...data].reverse()}
    />
  );
  return (
    <ChartCard title="Average rating by month" subtitle="Star rating, 1–5" table={table}>
      {data.length ? (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 11, fill: MUTED }} axisLine={{ stroke: AXIS }} tickLine={false} minTickGap={24} />
            <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fontSize: 11, fill: MUTED }} axisLine={false} tickLine={false} />
            <Tooltip content={<Tip />} cursor={{ stroke: AXIS, strokeWidth: 1 }} />
            <Line
              type="monotone"
              dataKey="avg_rating"
              stroke={SERIES}
              strokeWidth={2}
              dot={{ r: 4, fill: SERIES, stroke: SURFACE, strokeWidth: 2 }}
              activeDot={{ r: 5, fill: SERIES, stroke: SURFACE, strokeWidth: 2 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-sm text-slate-500">No dated reviews in this selection.</p>
      )}
    </ChartCard>
  );
}
