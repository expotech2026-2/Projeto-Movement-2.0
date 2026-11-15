// Alvo mostrado no painel: o comando do professor vale na hora; sem ele, o alvo que o ESP32 informou.
export function airTarget(reading, control, now = Date.now()) {
  const expires = Date.parse(control?.expires_at ?? "");
  const active =
    control && control.mode !== "auto" && (!Number.isFinite(expires) || expires > now);
  if (active && control.mode === "manual" && control.target != null) {
    return { target: control.target, source: "manual" };
  }
  if (active && control.mode === "off") return { target: null, source: "off" };
  if (reading) return { target: reading.target_temp, source: "sensor" };
  return { target: null, source: "none" };
}
