import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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
          stroke="#e9eeee"
        />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 11 }}
          minTickGap={60}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          unit="°"
          tick={{ fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip />
        <Line
          type="monotone"
          dataKey="temp_inside"
          name="Interna (°C)"
          stroke="#149b85"
          strokeWidth={2.5}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="temp_outside"
          name="Externa (°C)"
          stroke="#92b8cd"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
