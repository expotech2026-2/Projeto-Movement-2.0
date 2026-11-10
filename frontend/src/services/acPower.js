// Estado do ar para o botão Ligar/Desligar do painel da sala.

// O comando do site vale primeiro; no automático, vale o que o ESP32 informou por último.
export function acIsOn(control, device, reading) {
  if (control?.mode === "off") return false;
  if (control?.mode === "manual") return true;
  if (device?.ac_state) return device.ac_state.startsWith("ligado");
  return Boolean(reading?.ac_on);
}

// Ligar fixa a temperatura escolhida (o ar liga mesmo com a sala vazia); desligar força o off.
export function powerCommand(isOn, target) {
  return isOn ? { mode: "off" } : { mode: "manual", target };
}

// O ESP32 ainda não sabe o código IR do aparelho: o comando não chega ao ar.
export function missingIrProtocol(device) {
  return Boolean(device?.ac_state?.startsWith("sem protocolo"));
}
