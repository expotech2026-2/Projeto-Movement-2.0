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

// O ESP32 envia a cada 15 a 300 s; um intervalo maior que este é falta de leitura.
export const GAP_MS = 10 * 60 * 1000;

export function timeLabel(timestamp) {
  return TIME_LABEL.format(new Date(timestamp));
}

// 0 °C com 0% de umidade é o quadro zerado de um DHT com falha, não uma medição.
export function isSensorFailure(reading) {
  return reading.temp_inside === 0 && reading.humidity_inside === 0;
}

// Leituras das últimas `hours` horas no eixo de tempo; períodos sem leitura viram lacuna.
export function chartPoints(history, now, hours, gapMs = GAP_MS) {
  const from = now - hours * 3600000;
  const points = [];
  for (const item of history) {
    const timestamp = measuredAt(item);
    if (!(timestamp >= from) || isSensorFailure(item)) continue;
    const previous = points[points.length - 1];
    if (previous && timestamp - previous.timestamp > gapMs) {
      points.push({
        timestamp: (previous.timestamp + timestamp) / 2,
        gap: true,
        temp_inside: null,
        temp_outside: null,
      });
    }
    points.push({ ...item, timestamp });
  }
  // Leitura sem vizinhas próximas não forma linha; o gráfico a desenha como ponto.
  const isReading = (point) => Boolean(point) && !point.gap;
  return points.map((point, index) =>
    point.gap
      ? point
      : {
          ...point,
          alone: !isReading(points[index - 1]) && !isReading(points[index + 1]),
        },
  );
}
