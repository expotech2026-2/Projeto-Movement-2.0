// Busca sem acento e sem maiúsculas: "sao" encontra "São Paulo".
export function normalize(text) {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

// Texto gravado na unidade: o nome com a UF, porque há nomes repetidos entre estados.
export function cityLabel(city) {
  return `${city.name} - ${city.state}`;
}

function splitQuery(query) {
  const match = /^(.*\S)\s*-\s*([a-z]{2})$/i.exec(query.trim());
  return match
    ? { name: match[1], state: match[2].toUpperCase() }
    : { name: query.trim(), state: null };
}

// Ordem: começa com o texto antes de só contém; dentro de cada grupo, SP primeiro.
export function matchCities(cities, query, limit = 8) {
  const { name, state } = splitQuery(query);
  const wanted = normalize(name);
  if (!wanted) return [];
  const groups = [[], [], [], []];
  for (const city of cities) {
    if (state && city.state !== state) continue;
    const index = normalize(city.name).indexOf(wanted);
    if (index < 0) continue;
    const group = (index === 0 ? 0 : 2) + (city.state === "SP" ? 0 : 1);
    groups[group].push({ ...city, start: index, end: index + wanted.length });
  }
  return groups.flat().slice(0, limit);
}
