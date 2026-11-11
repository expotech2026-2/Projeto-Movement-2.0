import { normalize } from "./cityMatch";

// Sem espaço, hífen, ponto ou barra: "s4-q12" acha "S4Q12JA3WF" e "12.000" acha 12000.
const compact = (text) => normalize(text).replace(/[\s\-_./]/g, "");

// Marcas do catálogo do Inmetro: as que começam com o texto vêm antes das que só o contêm.
export function matchBrands(brands, query, limit = 8) {
  const wanted = compact(query);
  if (!wanted) return [];
  const starts = [];
  const contains = [];
  for (const item of brands) {
    const index = compact(item.brand).indexOf(wanted);
    if (index === 0) starts.push(item);
    else if (index > 0) contains.push(item);
  }
  return [...starts, ...contains].slice(0, limit);
}

export function findBrand(brands, text) {
  const wanted = compact(text);
  return wanted ? brands.find((item) => compact(item.brand) === wanted) : undefined;
}

// Cada palavra precisa aparecer no modelo, na evaporadora, na capacidade ou em "inverter".
export function matchModels(models, query, limit = 12) {
  const words = normalize(query).split(/\s+/).map(compact).filter(Boolean);
  if (!words.length) return [];
  const starts = [];
  const contains = [];
  for (const item of models) {
    const model = compact(item.model);
    const text = [
      model,
      compact(item.indoor_unit || ""),
      String(item.capacity_btu),
      item.inverter ? "inverter" : "convencional",
    ].join(" ");
    if (!words.every((word) => text.includes(word))) continue;
    (model.startsWith(words[0]) ? starts : contains).push(item);
  }
  return [...starts, ...contains].slice(0, limit);
}
