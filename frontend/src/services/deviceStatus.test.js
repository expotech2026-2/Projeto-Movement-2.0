import { describe, expect, it } from "vitest";
import {
  deviceStatus,
  formatDuration,
  sensorsLabel,
  signalLabel,
} from "./deviceStatus";

describe("status do ESP32", () => {
  it("mostra online, offline, nunca conectado e sem cadastro", () => {
    expect(deviceStatus({ online: true, seconds_since_contact: 12 })).toEqual({
      tone: "success",
      label: "ESP32 online · há 12 s",
    });
    expect(deviceStatus({ online: false, seconds_since_contact: 480 })).toEqual({
      tone: "danger",
      label: "ESP32 offline há 8 min",
    });
    expect(deviceStatus({ online: false, seconds_since_contact: null }).label).toBe(
      "ESP32 nunca conectou",
    );
    expect(deviceStatus(undefined).label).toBe("Sem ESP32 cadastrado");
  });

  it("escreve durações em s, min, h e dias", () => {
    expect(formatDuration(59)).toBe("59 s");
    expect(formatDuration(3599)).toBe("59 min");
    expect(formatDuration(3 * 3600 + 120)).toBe("3 h 2 min");
    expect(formatDuration(2 * 86400 + 5 * 3600)).toBe("2 d 5 h");
  });

  it("classifica o sinal Wi-Fi e as falhas dos sensores", () => {
    expect(signalLabel(-55)).toBe("ótimo (-55 dBm)");
    expect(signalLabel(-70)).toBe("bom (-70 dBm)");
    expect(signalLabel(-78)).toBe("fraco (-78 dBm)");
    expect(signalLabel(-90)).toBe("muito fraco (-90 dBm)");
    expect(signalLabel(null)).toBe("—");
    expect(sensorsLabel("ok")).toBe("Sem falhas");
    expect(sensorsLabel("DHT externo (GPIO 14)")).toBe("Falha: DHT externo (GPIO 14)");
    expect(sensorsLabel(null)).toBe("—");
  });
});
