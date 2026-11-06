import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { samplingPlan } from "../services/movementApi";

const BUDGETS = [
  ["0.3", "Orçamento: 30% da energia atual"],
  ["0.5", "Orçamento: 50% da energia atual"],
  ["0.7", "Orçamento: 70% da energia atual"],
  ["1", "Orçamento: 100% da energia atual"],
];

const axisTick = { fill: "var(--chart-axis)" };

function format(value, digits = 1) {
  return Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export default function SamplingPlan({ roomId }) {
  const [budget, setBudget] = useState("0.5");
  const [result, setResult] = useState({ key: null, plan: null, error: "" });
  const key = `${roomId}:${budget}`;

  useEffect(() => {
    let active = true;
    const requested = `${roomId}:${budget}`;
    samplingPlan(roomId, budget)
      .then((plan) => {
        if (active) setResult({ key: requested, plan, error: "" });
      })
      .catch((error) => {
        if (active)
          setResult({ key: requested, plan: null, error: error.message });
      });
    return () => {
      active = false;
    };
  }, [roomId, budget]);

  const { plan, error } = result;
  const loading = result.key !== key;
  const fromHistory = plan
    ? plan.hours.filter((hour) => hour.source === "history").length
    : 0;
  const metrics = plan
    ? [
        ["Energia/dia (otimizado)", `${format(plan.energy_j)} J`],
        ["Energia/dia (fixo 16 s)", `${format(plan.baseline_energy_j)} J`],
        ["Economia", `${format(plan.saving_percent)}%`],
        ["Erro esperado", `${format(plan.expected_error_c, 3)} °C`],
      ]
    : [];

  return (
    <section className="panel chart-panel">
      <div className="section-heading">
        <div>
          <h2>Plano de leitura otimizado</h2>
          <p className="muted">
            Intervalo de envio do sensor em cada hora, calculado por programação
            linear inteira
          </p>
        </div>
        <select
          aria-label="Orçamento de energia"
          value={budget}
          onChange={(event) => setBudget(event.target.value)}
        >
          {BUDGETS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {loading ? (
        <p className="muted">Calculando plano…</p>
      ) : error ? (
        <p className="notice error">{error}</p>
      ) : (
        <>
          <div className="sampling-metrics">
            {metrics.map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={plan.hours.map((hour) => ({
                  hour: `${hour.hour}h`,
                  interval: hour.interval_seconds,
                }))}
                margin={{ top: 10, right: 10, bottom: 0, left: -10 }}
              >
                <CartesianGrid
                  strokeDasharray="3 5"
                  vertical={false}
                  stroke="var(--chart-grid)"
                />
                <XAxis
                  dataKey="hour"
                  tick={{ ...axisTick, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  unit=" s"
                  tick={{ ...axisTick, fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "var(--border)" }}
                  formatter={(value) => [`${value} s`, "Intervalo"]}
                  contentStyle={{
                    background: "var(--surface-raised)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    color: "var(--text)",
                  }}
                  labelStyle={{ color: "var(--muted)" }}
                />
                <Bar
                  dataKey="interval"
                  name="Intervalo"
                  fill="var(--chart-1)"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="chart-note">
            {fromHistory} de 24 horas estimadas pelo histórico da sala; as
            demais usam o perfil padrão de horário de aula. Energia por envio:{" "}
            {format(plan.energy_per_send_j, 2)} J.
          </p>
        </>
      )}
    </section>
  );
}
