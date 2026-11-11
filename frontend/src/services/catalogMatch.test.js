import { describe, expect, it } from "vitest";
import { findBrand, matchBrands, matchModels } from "./catalogMatch";

const BRANDS = [
  { brand: "ELGIN", models: 40 },
  { brand: "GREE", models: 120 },
  { brand: "LG", models: 300 },
  { brand: "SPRINGER MIDEA", models: 90 },
  { brand: "MIDEA", models: 200 },
];

const MODELS = [
  { id: 1, model: "S4-Q12JA3WF", indoor_unit: "S4NQ12JA3WF", capacity_btu: 12000, inverter: true },
  { id: 2, model: "S4-Q18KL3WF", indoor_unit: "S4NQ18KL3WF", capacity_btu: 18000, inverter: true },
  { id: 3, model: "TSNC122", indoor_unit: "TS-H122", capacity_btu: 12000, inverter: false },
  { id: 4, model: "Q1-BASIC", indoor_unit: "", capacity_btu: 9000, inverter: false },
];

describe("sugestões do catálogo do Inmetro", () => {
  it("sugere marcas que começam com o texto antes das que o contêm", () => {
    expect(matchBrands(BRANDS, "mid").map((item) => item.brand)).toEqual([
      "MIDEA",
      "SPRINGER MIDEA",
    ]);
    expect(matchBrands(BRANDS, "  g ").map((item) => item.brand)).toEqual([
      "GREE",
      "ELGIN",
      "LG",
      "SPRINGER MIDEA",
    ]);
    expect(matchBrands(BRANDS, "")).toEqual([]);
  });

  it("reconhece a marca digitada inteira, sem diferença de maiúsculas ou espaços", () => {
    expect(findBrand(BRANDS, "springer midea")?.brand).toBe("SPRINGER MIDEA");
    expect(findBrand(BRANDS, "Springer")).toBeUndefined();
    expect(findBrand(BRANDS, "")).toBeUndefined();
  });

  it("acha o modelo sem hífen, pela evaporadora ou pela capacidade", () => {
    expect(matchModels(MODELS, "s4q12").map((item) => item.id)).toEqual([1]);
    expect(matchModels(MODELS, "TS-H122").map((item) => item.id)).toEqual([3]);
    expect(matchModels(MODELS, "12.000").map((item) => item.id)).toEqual([1, 3]);
    expect(matchModels(MODELS, "12000 inverter").map((item) => item.id)).toEqual([1]);
    expect(matchModels(MODELS, "  ")).toEqual([]);
  });

  it("põe primeiro os modelos que começam com o texto", () => {
    expect(matchModels(MODELS, "q1").map((item) => item.id)).toEqual([4, 1, 2]);
  });
});
