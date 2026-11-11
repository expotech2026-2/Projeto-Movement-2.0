import { describe, expect, it } from "vitest";
import { computerRule, computersOn, isLab, roomVolume } from "./roomHeat";

describe("computersOn", () => {
  it("liga uma máquina a cada 2 alunos numa sala comum", () => {
    expect([0, 1, 2, 9, 30].map((people) => computersOn(people, 10, 40))).toEqual([
      0, 0, 1, 4, 10,
    ]);
  });

  it("liga uma por aluno quando há computadores para quase todos", () => {
    expect([2, 30, 35].map((people) => computersOn(people, 30, 35))).toEqual([2, 30, 30]);
  });

  it("usa 80% da capacidade como limite do laboratório", () => {
    expect([isLab(35, 28), isLab(35, 27), isLab(35, 0)]).toEqual([true, false, false]);
  });

  it("explica a regra no cadastro da sala", () => {
    expect(computerRule(35, 0)).toMatch(/só as pessoas/);
    expect(computerRule(35, 30)).toMatch(/^Laboratório/);
    expect(computerRule(40, 10)).toMatch(/a cada 2 alunos/);
  });
});

describe("roomVolume", () => {
  it("usa a área informada vezes o pé-direito", () => {
    expect(roomVolume(72, 3, 60)).toBe(216);
  });

  it("estima 1,5 m² por pessoa quando a área está vazia", () => {
    expect([60, 70, 80].map((capacity) => roomVolume(null, 3, capacity))).toEqual([
      270, 315, 360,
    ]);
  });

  it("não usa menos de 20 m³", () => {
    expect(roomVolume(null, 3, 1)).toBe(20);
  });
});
