"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
    const key = chart.y[0] ?? columns[0];
    const value = rows[0]?.[columns.indexOf(key)];
    return (
      <div className="rounded-[var(--radius-md)] border border-border bg-surface px-5 py-6">
        <p className="text-xs uppercase tracking-wide text-text-muted">{key}</p>
        <p className="mt-1 font-data text-3xl font-medium">{formatCellValue(value)}</p>
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
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={nameKey}
            outerRadius={90}
            label={(entry: PieLabelRenderProps) =>
              String((entry as unknown as Record<string, unknown>)[nameKey])
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
    <div className="h-64 rounded-[var(--radius-md)] border border-border bg-surface p-3">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}
