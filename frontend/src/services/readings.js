// Histórico do painel: depois da primeira carga, só as leituras novas são pedidas à API.

export const HISTORY_LIMIT = 2000;
// O ESP32 reenvia uma leitura que falhou; a folga cobre as que chegam com alguns minutos de atraso.
const OVERLAP_MS = 10 * 60 * 1000;

function measuredAt(reading) {
  return Date.parse(reading.measured_at);
}

// Momento a partir do qual pedir leituras; null quando ainda não há nenhuma.
export function historySince(history, overlapMs = OVERLAP_MS) {
  if (!history.length) return null;
  const last = measuredAt(history[history.length - 1]);
  return Number.isFinite(last)
    ? new Date(last - overlapMs).toISOString()
    : null;
}

// Junta as leituras novas às que o painel já tem, sem repetir, da mais antiga à mais nova.
export function mergeReadings(previous, incoming, limit = HISTORY_LIMIT) {
  if (!incoming.length) return previous;
  const byId = new Map(previous.map((item) => [item.id, item]));
  for (const item of incoming) byId.set(item.id, item);
  return [...byId.values()]
    .sort((a, b) => measuredAt(a) - measuredAt(b))
    .slice(-limit);
}

const TIME_LABEL = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

// Leituras das últimas `hours` horas, com o rótulo de data e hora usado nos gráficos.
export function chartPoints(history, now, hours) {
  const from = now - hours * 3600000;
  return history
    .filter((item) => measuredAt(item) >= from)
    .map((item) => ({
      ...item,
      time: TIME_LABEL.format(new Date(item.measured_at)),
    }));
}
