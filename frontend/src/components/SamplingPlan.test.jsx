import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PlanResult } from "./SamplingPlan";

const missing = (hour) => ({
  hour,
  interval_seconds: null,
  occupancy: null,
  temp_rate: null,
  source: "missing",
});

describe("Plano de leitura", () => {
  it("sem leituras reais mostra o estado vazio e nenhum número", () => {
    const plan = {
      hours: Array.from({ length: 24 }, (_, hour) => missing(hour)),
      observed_hours: 0,
      energy_j: null,
      baseline_energy_j: null,
      saving_percent: null,
      expected_error_c: null,
      energy_per_send_j: 0.32,
    };
    const html = renderToStaticMarkup(createElement(PlanResult, { plan }));
    expect(html).toContain("Ainda sem dados suficientes");
    expect(html).not.toContain("Economia");
    expect(html).not.toContain(" J<");
  });

  it("diz quantas horas têm leituras reais", () => {
    const hours = Array.from({ length: 24 }, (_, hour) => missing(hour));
    hours[10] = {
      hour: 10,
      interval_seconds: 30,
      occupancy: 1,
      temp_rate: 0.01,
      source: "history",
    };
    const plan = {
      hours,
      observed_hours: 1,
      energy_j: 38.4,
      baseline_energy_j: 72,
      saving_percent: 46.7,
      expected_error_c: 0.3,
      energy_per_send_j: 0.32,
    };
    const html = renderToStaticMarkup(createElement(PlanResult, { plan }));
    expect(html).toContain("1 de 24 horas têm leituras reais");
    expect(html).toContain("46,7%");
    expect(html).not.toContain("perfil padrão");
  });
});
