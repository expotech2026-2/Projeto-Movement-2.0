import { describe, expect, it } from "vitest";
import { airTarget } from "./airTarget";

const NOW = Date.parse("2026-11-14T15:00:00Z");
const reading = { target_temp: 24 };

describe("airTarget", () => {
  it("usa a temperatura fixada pelo professor assim que o comando é salvo", () => {
    const control = { mode: "manual", target: 17, expires_at: "2026-11-14T16:46:00Z" };
    expect(airTarget(reading, control, NOW)).toEqual({ target: 17, source: "manual" });
  });

  it("mostra o ar desligado enquanto o comando de desligar vale", () => {
    const control = { mode: "off", target: null, expires_at: "2026-11-14T16:00:00Z" };
    expect(airTarget(reading, control, NOW)).toEqual({ target: null, source: "off" });
  });

  it("volta ao alvo informado pelo ESP32 no automático ou quando o comando expira", () => {
    expect(airTarget(reading, { mode: "auto", target: null }, NOW)).toEqual({
      target: 24,
      source: "sensor",
    });
    const expired = { mode: "manual", target: 17, expires_at: "2026-11-14T14:59:00Z" };
    expect(airTarget(reading, expired, NOW)).toEqual({ target: 24, source: "sensor" });
    expect(airTarget(reading, null, NOW)).toEqual({ target: 24, source: "sensor" });
  });

  it("sem leitura nem comando, não há alvo", () => {
    expect(airTarget(null, null, NOW)).toEqual({ target: null, source: "none" });
  });
});
