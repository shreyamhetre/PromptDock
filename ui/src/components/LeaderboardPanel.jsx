import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { p } from "../api.js";
import { formatDate, useApi } from "../useApi.js";
import { ErrorNotice } from "./common.jsx";

const fmt = (value) => (value == null ? "–" : Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 }));

function ChartTooltip({ active, payload, metric }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="tooltip">
      <strong>v{row.version}</strong>
      {row.tags.length > 0 && <span className="muted"> ({row.tags.join(", ")})</span>}
      <div>
        {metric}: {fmt(row[metric])}
      </div>
    </div>
  );
}

// One small chart per metric: metrics have different scales, so they never share a y-axis.
// A single series per chart needs no legend; the title names the metric.
function MetricChart({ metric, rows }) {
  const data = [...rows]
    .sort((a, b) => a.version - b.version)
    .map((r) => ({ version: r.version, tags: r.tags, [metric]: r.scores[metric] }));
  return (
    <div className="card">
      <div className="chart-title">{metric}</div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
        Latest score per version
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="version"
            tickFormatter={(v) => `v${v}`}
            stroke="var(--text-muted)"
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            tickLine={false}
          />
          <YAxis
            width={48}
            stroke="var(--text-muted)"
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            domain={["auto", "auto"]}
          />
          <Tooltip
            content={<ChartTooltip metric={metric} />}
            cursor={{ stroke: "var(--text-muted)", strokeWidth: 1 }}
          />
          <Line
            type="linear"
            dataKey={metric}
            stroke="var(--series-1)"
            strokeWidth={2}
            dot={{ r: 4, fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 }}
            activeDot={{ r: 6, fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function LeaderboardPanel({ name, reloadKey }) {
  const [sort, setSort] = useState({ by: "version", desc: true });
  const { data, error } = useApi(
    `${p(name)}/leaderboard`,
    { sort: sort.by, order: sort.desc ? "desc" : "asc" },
    reloadKey,
  );

  if (error) return <ErrorNotice error={error} />;
  if (!data) return <p className="muted">Loading…</p>;

  const header = (key, label, numeric = false) => {
    const active = sort.by === key;
    return (
      <th
        className={`sortable${numeric ? " num" : ""}`}
        onClick={() => setSort({ by: key, desc: active ? !sort.desc : true })}
        aria-sort={active ? (sort.desc ? "descending" : "ascending") : "none"}
      >
        {label} {active ? (sort.desc ? "▼" : "▲") : ""}
      </th>
    );
  };

  return (
    <>
      {data.metrics.length === 0 && (
        <div className="notice warn">
          ⚠️ No eval results yet. Send some with <code>promptdock evals push results.jsonl</code>.
        </div>
      )}
      <table>
        <thead>
          <tr>
            {header("version", "Version")}
            <th>Tags</th>
            {header("created_at", "Created")}
            {data.metrics.map((m) => header(m, m, true))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row) => (
            <tr key={row.version}>
              <td>
                <strong>v{row.version}</strong>
              </td>
              <td>
                {row.tags.map((t) => (
                  <span className="chip" key={t}>
                    {t}
                  </span>
                ))}
              </td>
              <td className="subtle">{formatDate(row.created_at)}</td>
              {data.metrics.map((m) => (
                <td key={m} className="num">
                  {fmt(row.scores[m])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.metrics.length > 0 && (
        <div className="charts">
          {data.metrics.map((m) => (
            <MetricChart key={m} metric={m} rows={data.rows} />
          ))}
        </div>
      )}
    </>
  );
}
