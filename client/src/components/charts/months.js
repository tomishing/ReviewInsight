import { addMonths, format, parse } from "date-fns";

// Fill missing months between the first and last so the time axis is evenly spaced.
export function fillMonths(monthly) {
  if (!monthly.length) return [];
  const byMonth = Object.fromEntries(monthly.map((m) => [m.month, m]));
  const out = [];
  let d = parse(monthly[0].month, "yyyy-MM", new Date());
  const last = monthly[monthly.length - 1].month;
  for (let i = 0; i < 600; i++) {
    const key = format(d, "yyyy-MM");
    out.push(byMonth[key] || { month: key, reviews: 0, avg_rating: null, analysed: 0, positive: 0, neutral: 0, negative: 0 });
    if (key === last) break;
    d = addMonths(d, 1);
  }
  return out;
}

export const monthLabel = (key) => format(parse(key, "yyyy-MM", new Date()), "MMM yy");
export const monthLong = (key) => format(parse(key, "yyyy-MM", new Date()), "MMMM yyyy");
