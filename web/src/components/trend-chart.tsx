export type TrendPoint = { label: string; value: number };

export function TrendChart({ title, points, threshold = 150 }: {
  title: string;
  points: TrendPoint[];
  threshold?: number;
}) {
  if (!points.length) return <p className="muted">No readings available to chart.</p>;
  const width = 640;
  const height = 260;
  const padding = { top: 18, right: 20, bottom: 42, left: 42 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(threshold, ...points.map((point) => point.value), 1);
  const yMax = Math.ceil(maxValue / 50) * 50 || 50;
  const x = (index: number) => padding.left + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const y = (value: number) => padding.top + plotHeight - (value / yMax) * plotHeight;
  const line = points.map((point, index) => `${x(index)},${y(point.value)}`).join(" ");
  const labelCount = Math.min(points.length, 6);
  const dateLabelIndices = new Set(Array.from(
    { length: labelCount },
    (_, index) => labelCount === 1 ? 0 : Math.round(index * (points.length - 1) / (labelCount - 1)),
  ));
  const tickCount = 4;

  return <div className="card chart-card">
    <h3>{title}</h3>
    <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}. ${points.map((point) => `${point.label}: API ${point.value}`).join("; ")}`}>
      <title>{title}</title>
      {Array.from({ length: tickCount + 1 }, (_, index) => {
        const value = (yMax / tickCount) * index;
        return <g key={index}>
          <line className="chart-grid" x1={padding.left} x2={width - padding.right} y1={y(value)} y2={y(value)} />
          <text className="chart-axis" x={padding.left - 8} y={y(value) + 4} textAnchor="end">{Math.round(value)}</text>
        </g>;
      })}
      {threshold <= yMax && <g>
        <line className="chart-threshold" x1={padding.left} x2={width - padding.right} y1={y(threshold)} y2={y(threshold)} />
        <text className="chart-label" x={width - padding.right} y={y(threshold) - 5} textAnchor="end">Trigger {threshold}</text>
      </g>}
      {points.length > 1 && <polyline className="chart-line" points={line} />}
      {points.map((point, index) => <g key={`${point.label}-${index}`}>
        <circle className="chart-dot" cx={x(index)} cy={y(point.value)} r="5"><title>{point.label}: API {point.value}</title></circle>
        {dateLabelIndices.has(index) &&
          <text className="chart-label" x={x(index)} y={height - 14} textAnchor="middle">{point.label}</text>}
      </g>)}
    </svg>
    <div className="chart-legend"><span><i className="chart-key" />Daily API</span><span><i className="chart-key alert" />Trigger threshold</span></div>
  </div>;
}

export function BarChart({ title, items, highlightAbove }: {
  title: string;
  items: { label: string; value: number }[];
  highlightAbove?: number;
}) {
  const rows = items.slice(0, 12);
  if (!rows.length) return <article className="card chart-card"><h3>{title}</h3><p className="muted">No data available to chart yet.</p></article>;
  const width = 640;
  const rowHeight = 34;
  const height = Math.max(150, rows.length * rowHeight + 34);
  const labelWidth = 160;
  const valueWidth = 38;
  const barWidth = width - labelWidth - valueWidth - 24;
  const maxValue = Math.max(1, ...rows.map((item) => item.value));

  return <article className="card chart-card">
    <h3>{title}</h3>
    <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}. ${rows.map((item) => `${item.label}: ${item.value}`).join("; ")}`}>
      <title>{title}</title>
      {rows.map((item, index) => {
        const y = 14 + index * rowHeight;
        const length = (item.value / maxValue) * barWidth;
        return <g key={`${item.label}-${index}`}>
          <text className="chart-label" x="0" y={y + 18}>{item.label.length > 22 ? `${item.label.slice(0, 20)}…` : item.label}</text>
          <rect className="chart-track" x={labelWidth} y={y + 4} width={barWidth} height="18" rx="8" />
          <rect className={highlightAbove !== undefined && item.value > highlightAbove ? "chart-bar-alert" : "chart-bar"} x={labelWidth} y={y + 4} width={Math.max(0, length)} height="18" rx="8" />
          <text className="chart-axis" x={labelWidth + barWidth + 8} y={y + 18}>{item.value}</text>
        </g>;
      })}
    </svg>
  </article>;
}
