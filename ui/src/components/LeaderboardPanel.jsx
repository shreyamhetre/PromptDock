import { useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { p } from "../api.js";
import { useApi } from "../useApi.js";
import {
  ErrorNotice,
  TagPill,
  metricDirection,
  metricFormatter,
  timeAgo,
} from "./common.jsx";

// Round, evenly spaced axis ticks around [lo, hi] with a little headroom.
function niceScale(lo, hi, count = 5) {
  const span = hi - lo || Math.abs(hi) || 1;
  const raw = (span * 1.3) / (count - 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw);
  let start = Math.floor((lo - span * 0.15) / step) * step;
  if (lo >= 0 && start < 0) start = 0;
  const end = Math.ceil((hi + span * 0.15) / step) * step;
  const ticks = [];
  for (let t = start; t <= end + step / 2; t += step) ticks.push(Number(t.toFixed(10)));
  return { ticks, domain: [ticks[0], ticks[ticks.length - 1]] };
}

// Threshold a gate puts on this metric, for the chart's reference line.
function gateLines(metric, tags) {
  const lines = [];
  for (const tag of tags) {
    for (const rule of tag.gate?.rules || []) {
      if (rule.metric !== metric) continue;
      if (rule.min != null) lines.push({ y: rule.min, label: `${tag.name} gate ≥ ${rule.min}` });
      if (rule.max != null) lines.push({ y: rule.max, label: `${tag.name} gate ≤ ${rule.max}` });
    }
  }
  return lines;
}

function ChartTooltip({ active, payload, format, metric }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  if (row.value == null) return null;
  return (
    <div className="tooltip">
      <div className="t-head">
        v{row.version}
        {row.tags.length > 0 && <span className="muted"> · {row.tags.join(", ")}</span>}
      </div>
      <div>
        {metric}: <strong className="num">{format(row.value)}</strong>
      </div>
    </div>
  );
}

function MetricChart({ metric, rows, tags, format }) {
  const data = [...rows]
    .sort((a, b) => a.version - b.version)
    .map((r) => ({ version: r.version, tags: r.tags, value: r.scores[metric] }));
  const scored = data.filter((d) => d.value != null);
  const lines = gateLines(metric, tags);

  if (scored.length < 2) {
    const only = scored[0];
    return (
      <div className="single-value">
        <span className="big">{only ? format(only.value) : "–"}</span>
        <span className="muted">
          {only
            ? `Only v${only.version} has a ${metric} result so far — a trend appears once two versions are scored.`
            : `No ${metric} results yet.`}
        </span>
      </div>
    );
  }

  const values = [...scored.map((d) => d.value), ...lines.map((l) => l.y)];
  const { ticks, domain } = niceScale(Math.min(...values), Math.max(...values));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 16, right: 24, bottom: 4, left: 4 }}>
        <CartesianGrid stroke="var(--grid)" strokeWidth={1} vertical={false} />
        <XAxis
          dataKey="version"
          tickFormatter={(v) => `v${v}`}
          stroke="var(--border-strong)"
          tick={{ fill: "var(--text-3)", fontSize: 12 }}
          tickLine={false}
          padding={{ left: 16, right: 16 }}
        />
        <YAxis
          width={64}
          domain={domain}
          ticks={ticks}
          tickFormatter={(v) => format(v, false)}
          tick={{ fill: "var(--text-3)", fontSize: 12 }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          content={<ChartTooltip format={format} metric={metric} />}
          cursor={{ stroke: "var(--border-strong)", strokeWidth: 1 }}
        />
        {lines.map((line) => (
          <ReferenceLine
            key={line.label}
            y={line.y}
            stroke="var(--text-3)"
            strokeDasharray="4 4"
            label={{
              value: line.label,
              position: "insideTopRight",
              fill: "var(--text-3)",
              fontSize: 11.5,
            }}
          />
        ))}
        <Area
          type="linear"
          dataKey="value"
          fill="var(--series-1-wash)"
          stroke="none"
          connectNulls
          isAnimationActive={false}
          activeDot={false}
        />
        <Line
          type="linear"
          dataKey="value"
          stroke="var(--series-1)"
          strokeWidth={2}
          connectNulls
          dot={{ r: 4, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }}
          activeDot={{ r: 6, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export default function LeaderboardPanel({ name, tags, reloadKey }) {
  const [sort, setSort] = useState({ by: "version", desc: true });
  const { data, error } = useApi(
    `${p(name)}/leaderboard`,
    { sort: sort.by, order: sort.desc ? "desc" : "asc" },
    reloadKey,
  );
  const [chosen, setChosen] = useState(null);

  if (error) return <ErrorNotice error={error} />;
  if (!data) return <div className="skeleton" />;

  if (data.metrics.length === 0) {
    return (
      <div className="panel">
        <div className="empty">
          <strong>No eval results yet</strong>
          Send scores with <code>promptdock evals push results.jsonl</code> or{" "}
          <code>client.add_eval_results([...])</code>; they appear here per version.
        </div>
      </div>
    );
  }

  const columns = data.metrics.map((metric) => {
    const values = data.rows.map((r) => r.scores[metric]);
    const finite = values.filter((v) => v != null);
    const direction = metricDirection(metric, tags);
    const best = finite.length > 1 ? (direction === "higher" ? Math.max : Math.min)(...finite) : null;
    return {
      metric,
      direction,
      best,
      max: finite.length ? Math.max(...finite.map(Math.abs)) : 0,
      format: metricFormatter(values, metric),
    };
  });
  const metric = chosen && data.metrics.includes(chosen) ? chosen : data.metrics[0];
  const active = columns.find((c) => c.metric === metric);

  const header = (key, label, right = false, title = undefined) => {
    const on = sort.by === key;
    return (
      <th
        className={`sortable${right ? " right" : ""}`}
        title={title}
        onClick={() => setSort({ by: key, desc: on ? !sort.desc : true })}
        aria-sort={on ? (sort.desc ? "descending" : "ascending") : "none"}
      >
        {label}
        <span className="sort">{on ? (sort.desc ? "↓" : "↑") : ""}</span>
      </th>
    );
  };

  return (
    <>
      <div className="panel">
        <div className="panel-head">
          <h2>Scores by version</h2>
          <span className="hint">Latest result per metric · click a column to sort</span>
        </div>
        <table>
          <thead>
            <tr>
              {header("version", "Version")}
              <th>Tags</th>
              {header("created_at", "Saved")}
              {columns.map((c) =>
                header(
                  c.metric,
                  `${c.metric} ${c.direction === "higher" ? "↑" : "↓"}`,
                  true,
                  c.direction === "higher" ? "Higher is better" : "Lower is better",
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.version}>
                <td>
                  <strong className="mono">v{row.version}</strong>
                  {row.commit_message && <div className="muted">{row.commit_message}</div>}
                </td>
                <td>
                  {row.tags.map((t) => (
                    <TagPill key={t} name={t} />
                  ))}
                </td>
                <td className="muted nowrap">{timeAgo(row.created_at)}</td>
                {columns.map((c) => {
                  const value = row.scores[c.metric];
                  const isBest = value != null && value === c.best;
                  const width = value != null && c.max ? (Math.abs(value) / c.max) * 100 : 0;
                  return (
                    <td key={c.metric} className="right score-cell num">
                      <span className={`score-val${isBest ? " badge-best" : value == null ? " faint" : ""}`}>
                        {isBest && <span title="Best">★ </span>}
                        {c.format(value)}
                      </span>
                      {value != null && (
                        <span className="score-track">
                          <span className={`score-fill${isBest ? " best" : ""}`} style={{ width: `${width}%` }} />
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>{metric} over versions</h2>
          {data.metrics.length > 1 && (
            <div className="segmented" role="tablist">
              {data.metrics.map((m) => (
                <button key={m} className={m === metric ? "on" : ""} onClick={() => setChosen(m)}>
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="chart-wrap">
          <MetricChart metric={metric} rows={data.rows} tags={tags} format={active.format} />
        </div>
      </div>
    </>
  );
}
