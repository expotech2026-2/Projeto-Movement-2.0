import React, { useEffect, useState } from "react";
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

// Resultado do plano; sem horas com leituras reais, nenhum número é mostrado.
export function PlanResult({ plan }) {
  const observed = plan.observed_hours ?? 0;
  if (!observed) {
    return (
      <div className="chart-empty">
        <h3>Ainda sem dados suficientes</h3>
        <p>
          O plano é calculado só com leituras reais desta sala. Ele aparece
          quando o sensor tiver enviado alguns minutos seguidos de medições numa
          mesma hora; até lá, o ESP32 envia a cada 16 s.
        </p>
      </div>
    );
  }
  const metrics = [
    ["Energia/dia (otimizado)", `${format(plan.energy_j)} J`],
    ["Energia/dia (fixo 16 s)", `${format(plan.baseline_energy_j)} J`],
    ["Economia", `${format(plan.saving_percent)}%`],
    ["Erro esperado", `${format(plan.expected_error_c, 3)} °C`],
  ];
  return (
    <>
      <div className="sampling-metrics">
        {metrics.map(([label, value]) => (
          <div
            key={label}
            className={label === "Economia" ? "saving" : undefined}
          >
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
              formatter={(value) =>
                value == null
                  ? ["sem leituras reais", "Intervalo"]
                  : [`${value} s`, "Intervalo"]
              }
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
              fill="var(--chart-bar)"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="chart-note">
        {observed === 24
          ? "As 24 horas usam o histórico real da sala."
          : `${observed} de 24 horas têm leituras reais da sala; as demais ficam sem barra, fora da energia e do erro, e nelas o ESP32 envia a cada 16 s.`}{" "}
        Energia por envio (estimada): {format(plan.energy_per_send_j, 2)} J.
      </p>
    </>
  );
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
        <label className="field-inline">
          Orçamento de energia
          <select
            value={budget}
            onChange={(event) => setBudget(event.target.value)}
          >
            {BUDGETS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {loading ? (
        <p className="muted">Calculando plano…</p>
      ) : error ? (
        <p className="notice error">{error}</p>
      ) : (
        <PlanResult plan={plan} />
      )}
    </section>
  );
}
