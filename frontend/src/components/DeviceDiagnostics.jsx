import {
  deviceStatus,
  formatDuration,
  sensorsLabel,
  signalLabel,
} from "../services/deviceStatus";

export function StatusBadge({ device }) {
  const status = deviceStatus(device);
  const tone = status.tone === "danger" ? "offline" : status.tone;
  return <span className={`badge ${tone}`}>{status.label}</span>;
}

// Painel de manutenção: o que o ESP32 informou na última chamada à API.
export function DeviceDiagnostics({ device }) {
  if (!device) return null;
  const items = [
    [
      "Último contato",
      device.last_seen_at
        ? new Date(device.last_seen_at).toLocaleString("pt-BR")
        : "Nunca",
    ],
    ["Sinal Wi-Fi", signalLabel(device.rssi)],
    [
      "Ligado há",
      device.uptime_seconds == null
        ? "—"
        : formatDuration(device.uptime_seconds),
    ],
    ["Sensores", sensorsLabel(device.sensor_faults)],
    ["Ar-condicionado", device.ac_state || "—"],
    ["Versão do código", device.firmware || "—"],
  ];
  return (
    <section
      className="panel diagnostics-panel"
      aria-label="Diagnóstico do ESP32"
    >
      <div className="section-heading">
        <div>
          <h2>Diagnóstico do ESP32</h2>
          <p className="muted">
            {device.id} · fica offline depois de 2,5 min sem contato
          </p>
        </div>
        <StatusBadge device={device} />
      </div>
      <dl className="diagnostics-grid">
        {items.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
