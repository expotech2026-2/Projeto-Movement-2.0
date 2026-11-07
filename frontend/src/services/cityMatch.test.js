import { describe, expect, it } from "vitest";
import { cityLabel, matchCities, normalize } from "./cityMatch";

const CITIES = [
  { id: 2201606, name: "Bom Jesus", state: "PI" },
  { id: 3506904, name: "Bom Jesus dos Perdões", state: "SP" },
  { id: 3509502, name: "Campinas", state: "SP" },
  { id: 4303509, name: "Campinas do Sul", state: "RS" },
  { id: 3545803, name: "Santa Bárbara d'Oeste", state: "SP" },
  { id: 3550308, name: "São Paulo", state: "SP" },
  { id: 3503208, name: "Araraquara", state: "SP" },
];

const names = (list) => list.map(cityLabel);

describe("Busca de municípios", () => {
  it("ignora acentos e maiúsculas", () => {
    expect(normalize("São Bárbara D'Oeste")).toBe("sao barbara d'oeste");
    expect(names(matchCities(CITIES, "SAO"))).toEqual(["São Paulo - SP"]);
  });

  it("põe quem começa com o texto antes e SP primeiro em cada grupo", () => {
    expect(names(matchCities(CITIES, "bom jesus"))).toEqual([
      "Bom Jesus dos Perdões - SP",
      "Bom Jesus - PI",
    ]);
    expect(names(matchCities(CITIES, "ar"))).toEqual([
      "Araraquara - SP",
      "Santa Bárbara d'Oeste - SP",
    ]);
  });

  it("marca o trecho achado no nome", () => {
    const [found] = matchCities(CITIES, "oeste");
    expect(found.name.slice(found.start, found.end)).toBe("Oeste");
  });

  it("filtra pela UF quando o texto termina com ela", () => {
    expect(names(matchCities(CITIES, "campinas - rs"))).toEqual([
      "Campinas do Sul - RS",
    ]);
    expect(names(matchCities(CITIES, "Campinas - SP"))).toEqual([
      "Campinas - SP",
    ]);
  });

  it("respeita o limite e não sugere nada com o campo vazio", () => {
    expect(matchCities(CITIES, "a", 3)).toHaveLength(3);
    expect(matchCities(CITIES, "   ")).toEqual([]);
  });
});
