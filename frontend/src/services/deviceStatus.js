// Textos do status do ESP32 a partir dos dados de GET /rooms/{id}/devices.

export function formatDuration(seconds) {
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ${minutes % 60} min`;
  return `${Math.floor(hours / 24)} d ${hours % 24} h`;
}

export function deviceStatus(device) {
  if (!device) return { tone: "warning", label: "Sem ESP32 cadastrado" };
  if (device.seconds_since_contact == null)
    return { tone: "warning", label: "ESP32 nunca conectou" };
  const ago = formatDuration(device.seconds_since_contact);
  return device.online
    ? { tone: "success", label: `ESP32 online · há ${ago}` }
    : { tone: "danger", label: `ESP32 offline há ${ago}` };
}

// Faixas usuais de RSSI do Wi-Fi do ESP32.
export function signalLabel(rssi) {
  if (rssi == null) return "—";
  const quality =
    rssi >= -60 ? "ótimo" : rssi >= -70 ? "bom" : rssi >= -80 ? "fraco" : "muito fraco";
  return `${quality} (${rssi} dBm)`;
}

export function sensorsLabel(faults) {
  if (faults == null) return "—";
  return faults === "ok" ? "Sem falhas" : `Falha: ${faults}`;
}
