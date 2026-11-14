import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { timeLabel } from "../services/readings";

const axisTick = { fill: "var(--chart-axis)" };

// Só a leitura isolada por lacunas ganha marcador; as demais já formam a linha.
function aloneDot({ cx, cy, stroke, payload, index }) {
  if (!payload.alone || cy == null) return null;
  return <circle key={index} cx={cx} cy={cy} r={3} fill={stroke} />;
}

export default function SensorChart({ points, range }) {
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
          dataKey="timestamp"
          type="number"
          scale="time"
          domain={range}
          allowDataOverflow
          tickFormatter={timeLabel}
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
          labelFormatter={timeLabel}
        />
        <Line
          type="monotone"
          dataKey="temp_inside"
          name="Interna (°C)"
          stroke="var(--chart-1)"
          strokeWidth={2.5}
          dot={aloneDot}
        />
        <Line
          type="monotone"
          dataKey="temp_outside"
          name="Externa (°C)"
          stroke="var(--chart-2)"
          strokeWidth={2}
          dot={aloneDot}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
