"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  type PieLabelRenderProps,
} from "recharts";
import { formatCellValue, toRecords } from "@/lib/format";
import type { AskResponse } from "@/lib/types";

// Mirrors --chart-1..6 in globals.css. Duplicated as plain hex rather than
// read via var() because SVG presentation-attribute support for CSS custom
// properties is still inconsistent across the browsers Recharts targets.
const CHART_COLORS = [
  "#0e5f56",
  "#b7791f",
  "#3b6e91",
  "#8a4b6b",
  "#5b7a3a",
  "#94582c",
];

const AXIS_TICK = { fontSize: 12, fill: "var(--text-muted)" };
const LEGEND_STYLE = { fontSize: 12, color: "var(--text-muted)", paddingTop: 8 };

function TooltipContent({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: unknown; color?: string }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-[var(--radius-sm)] border border-border bg-surface px-2.5 py-1.5 text-xs shadow-[var(--shadow-lift)]">
      {label !== undefined && <p className="mb-0.5 font-medium">{label}</p>}
      {payload.map((entry) => (
        <p key={entry.name} className="font-data" style={{ color: entry.color }}>
          {entry.name}: {formatCellValue(entry.value)}
        </p>
      ))}
    </div>
  );
}

/** Renders whatever `chart.type` the backend's rule engine picked
 * (app/query/charts.py) — this component makes no chart-selection decisions
 * of its own, it only draws the one it's told. A `type: "table"` result is
 * handled by the caller (Turn.tsx skips straight to the data table). */
export function ChartView({ result }: { result: AskResponse }) {
  const { chart, columns, rows } = result;
  const data = toRecords(columns, rows);

  if (chart.type === "kpi") {
    const keys = chart.y.length > 0 ? chart.y : [columns[0]];
    // One headline figure gets a large single tile; several (e.g. comparing
    // avg_bonus_2023 vs avg_bonus_2024) lay out side by side so they read as
    // "these figures relate to each other," not as unrelated stats.
    return (
      <div
        className={
          keys.length === 1
            ? "rounded-[var(--radius-md)] border border-border bg-surface px-5 py-6"
            : "grid grid-cols-2 gap-3 sm:grid-cols-3"
        }
      >
        {keys.map((key) => {
          const value = rows[0]?.[columns.indexOf(key)];
          return (
            <div
              key={key}
              className={
                keys.length === 1
                  ? undefined
                  : "rounded-[var(--radius-md)] border border-border bg-surface px-4 py-4"
              }
            >
              <p className="truncate text-xs uppercase tracking-wide text-text-muted">
                {key}
              </p>
              <p
                className={
                  keys.length === 1
                    ? "mt-1 font-data text-3xl font-medium"
                    : "mt-1 font-data text-xl font-medium"
                }
              >
                {formatCellValue(value)}
              </p>
            </div>
          );
        })}
      </div>
    );
  }

  if (chart.type === "line") {
    return (
      <ChartFrame>
        <LineChart data={data}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey={chart.x ?? undefined} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<TooltipContent />} />
          {chart.y.length > 1 && <Legend wrapperStyle={LEGEND_STYLE} />}
          {chart.y.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          ))}
        </LineChart>
      </ChartFrame>
    );
  }

  if (chart.type === "bar") {
    return (
      <ChartFrame>
        <BarChart data={data}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey={chart.x ?? undefined} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<TooltipContent />} cursor={{ fill: "var(--surface-sunken)" }} />
          {chart.y.length > 1 && <Legend wrapperStyle={LEGEND_STYLE} />}
          {chart.y.map((key, i) => (
            <Bar key={key} dataKey={key} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[2, 2, 0, 0]} />
          ))}
        </BarChart>
      </ChartFrame>
    );
  }

  if (chart.type === "pie") {
    const valueKey = chart.y[0];
    const nameKey = chart.x ?? columns[0];
    return (
      <ChartFrame>
        <PieChart>
          <Tooltip content={<TooltipContent />} />
          {/* Names go in the legend, not as inline labels — full names (an
           * employee, a long category) collide and overlap once you have
           * more than three or four slices; a percentage on the slice
           * itself plus a legend below stays legible at any label length. */}
          <Legend
            wrapperStyle={LEGEND_STYLE}
            formatter={(value) => (
              <span className="font-data text-text">{value}</span>
            )}
          />
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={nameKey}
            outerRadius={85}
            label={(entry: PieLabelRenderProps) =>
              entry.percent ? `${Math.round(entry.percent * 100)}%` : ""
            }
            labelLine={false}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Pie>
        </PieChart>
      </ChartFrame>
    );
  }

  if (chart.type === "scatter") {
    const xKey = chart.x ?? columns[0];
    const yKey = chart.y[0] ?? columns[1];
    return (
      <ChartFrame>
        <ScatterChart>
          <CartesianGrid stroke="var(--border)" />
          <XAxis dataKey={xKey} name={xKey} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
          <YAxis dataKey={yKey} name={yKey} tick={AXIS_TICK} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<TooltipContent />} cursor={{ stroke: "var(--border)" }} />
          <Scatter data={data} fill={CHART_COLORS[0]} />
        </ScatterChart>
      </ChartFrame>
    );
  }

  return null;
}

function ChartFrame({ children }: { children: React.ReactElement }) {
  return (
    <div className="h-72 rounded-[var(--radius-md)] border border-border bg-surface p-3 pb-1">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}
