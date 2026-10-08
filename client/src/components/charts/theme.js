// Chart tokens (dataviz reference palette, light surface).
// Sentiment keeps SPEC's green / gray / red, always in this order so gray separates green
// from red (green↔red alone is not colour-blind safe), and always with text labels.
export const SENTIMENT = [
  { key: "positive", label: "Positive", color: "#0ca30c" },
  { key: "neutral", label: "Neutral", color: "#898781" },
  { key: "negative", label: "Negative", color: "#d03b3b" },
];
export const SERIES = "#2a78d6"; // single-series marks
export const SERIES_HOVER = "#1c5cab";
export const GRID = "#e1e0d9";
export const AXIS = "#c3c2b7";
export const MUTED = "#898781";
export const INK_2 = "#52514e";
export const SURFACE = "#ffffff";

export const pct = (n, total) => (total ? Math.round((n / total) * 100) : 0);
