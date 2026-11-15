import { describe, expect, it } from "vitest";
import {
  chartPoints,
  historySince,
  isSensorFailure,
  mergeReadings,
  timeLabel,
} from "./readings";

const reading = (id, measured_at, temp_inside = 24) => ({
  id,
  measured_at,
  temp_inside,
});

describe("histórico incremental", () => {
  it("pede as leituras a partir da última, com dez minutos de folga", () => {
    expect(historySince([])).toBeNull();
    expect(
      historySince([
        reading("a", "2026-11-13T12:00:00Z"),
        reading("b", "2026-11-13T12:30:00Z"),
      ]),
    ).toBe("2026-11-13T12:20:00.000Z");
  });

  it("junta as novas sem repetir e mantém a ordem de medição", () => {
    const previous = [
      reading("a", "2026-11-13T12:00:00Z"),
      reading("b", "2026-11-13T12:00:15Z"),
    ];
    const merged = mergeReadings(previous, [
      reading("b", "2026-11-13T12:00:15Z", 25),
      reading("d", "2026-11-13T12:00:45Z"),
      reading("c", "2026-11-13T12:00:30.500000Z"),
    ]);
    expect(merged.map((item) => item.id)).toEqual(["a", "b", "c", "d"]);
    expect(merged[1].temp_inside).toBe(25);
    expect(previous).toHaveLength(2);
  });

  it("devolve a mesma lista quando nada chegou e respeita o limite", () => {
    const previous = [reading("a", "2026-11-13T12:00:00Z")];
    expect(mergeReadings(previous, [])).toBe(previous);
    const merged = mergeReadings(
      previous,
      [
        reading("b", "2026-11-13T12:00:15Z"),
        reading("c", "2026-11-13T12:00:30Z"),
      ],
      2,
    );
    expect(merged.map((item) => item.id)).toEqual(["b", "c"]);
  });

  it("monta os pontos do gráfico só com o período escolhido", () => {
    const now = Date.parse("2026-11-13T15:00:00Z");
    const points = chartPoints(
      [
        reading("velha", "2026-11-13T08:59:00Z"),
        reading("nova", "2026-11-13T14:00:00Z"),
      ],
      now,
      6,
    );
    expect(points.map((item) => item.id)).toEqual(["nova"]);
    expect(points[0].timestamp).toBe(Date.parse("2026-11-13T14:00:00Z"));
    expect(timeLabel(points[0].timestamp)).toBe(
      new Date("2026-11-13T14:00:00Z").toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }),
    );
  });

  it("abre uma lacuna quando o sensor fica mais de dez minutos sem enviar", () => {
    const now = Date.parse("2026-11-13T15:00:00Z");
    const points = chartPoints(
      [
        reading("a", "2026-11-13T14:00:00Z", 25),
        reading("b", "2026-11-13T14:05:00Z", 25.2),
        reading("c", "2026-11-13T14:40:00Z", 26),
      ],
      now,
      6,
    );
    expect(points.map((item) => item.id ?? "lacuna")).toEqual([
      "a",
      "b",
      "lacuna",
      "c",
    ]);
    expect(points[2].temp_inside).toBeNull();
    expect(points[2].temp_outside).toBeNull();
    expect(points.map((item) => item.alone)).toEqual([
      false,
      false,
      undefined,
      true,
    ]);
  });

  it("não desenha a leitura zerada de um DHT com falha", () => {
    const now = Date.parse("2026-11-13T15:00:00Z");
    const failure = {
      ...reading("falha", "2026-11-13T14:00:15Z", 0),
      humidity_inside: 0,
    };
    const cold = {
      ...reading("fria", "2026-11-13T14:00:30Z", 0),
      humidity_inside: 40,
    };
    expect(isSensorFailure(failure)).toBe(true);
    expect(isSensorFailure(cold)).toBe(false);
    const points = chartPoints(
      [reading("a", "2026-11-13T14:00:00Z"), failure, cold],
      now,
      6,
    );
    expect(points.map((item) => item.id)).toEqual(["a", "fria"]);
  });
});
