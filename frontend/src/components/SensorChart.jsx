import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const axisTick = { fill: "var(--chart-axis)" };

export default function SensorChart({ points }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart
        data={points}
        margin={{ top: 10, right: 10, bottom: 0, left: -18 }}
      >
        <CartesianGrid
          strokeDasharray="3 5"
          vertical={false}
          stroke="var(--chart-grid)"
        />
        <XAxis
          dataKey="time"
          tick={{ ...axisTick, fontSize: 11 }}
          minTickGap={60}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          unit="°"
          tick={{ ...axisTick, fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ stroke: "var(--border-strong)" }}
          contentStyle={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            color: "var(--text)",
          }}
          labelStyle={{ color: "var(--muted)" }}
        />
        <Line
          type="monotone"
          dataKey="temp_inside"
          name="Interna (°C)"
          stroke="var(--chart-1)"
          strokeWidth={2.5}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="temp_outside"
          name="Externa (°C)"
          stroke="var(--chart-2)"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
