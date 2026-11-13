import { describe, expect, it } from "vitest";
import { acIsOn, missingIrProtocol, powerCommand } from "./acPower";

describe("botão Ligar/Desligar do ar", () => {
  it("usa o pedido aceito pelo Xiaomi e mantém a leitura em falhas ou pendências", () => {
    expect(
      acIsOn(
        { mode: "auto" },
        { ac_state: "Xiaomi: pedido aceito: ligar 23 C" },
      ),
    ).toBe(true);
    expect(
      acIsOn(
        { mode: "auto" },
        { ac_state: "Xiaomi: pedido aceito: desligar" },
        { ac_on: true },
      ),
    ).toBe(false);
    for (const ac_state of [
      "Xiaomi: pedido pendente",
      "Xiaomi: falha HTTP -1, pedido pendente",
    ]) {
      expect(acIsOn({ mode: "auto" }, { ac_state }, { ac_on: true })).toBe(
        true,
      );
    }
  });
  it("segue o comando do site antes do que o ESP32 informou", () => {
    const ligado = { ac_state: "ligado 23 C, GREE" };
    const desligado = { ac_state: "desligado, GREE" };
    expect(acIsOn({ mode: "off" }, ligado)).toBe(false);
    expect(acIsOn({ mode: "manual" }, desligado)).toBe(true);
    expect(acIsOn({ mode: "auto" }, ligado)).toBe(true);
    expect(acIsOn({ mode: "auto" }, desligado)).toBe(false);
  });

  it("usa a última leitura quando o ESP32 não mandou o estado", () => {
    expect(acIsOn({ mode: "auto" }, { ac_state: null }, { ac_on: true })).toBe(
      true,
    );
    expect(acIsOn({ mode: "auto" }, undefined, undefined)).toBe(false);
    expect(acIsOn(null, undefined, { ac_on: false })).toBe(false);
  });

  it("liga fixando a temperatura e desliga com o modo off", () => {
    expect(powerCommand(false, 23)).toEqual({ mode: "manual", target: 23 });
    expect(powerCommand(true, 23)).toEqual({ mode: "off" });
  });

  it("avisa quando o ESP32 ainda não tem o protocolo IR", () => {
    expect(
      missingIrProtocol({ ac_state: "sem protocolo IR (rode IR_TESTE)" }),
    ).toBe(true);
    expect(missingIrProtocol({ ac_state: "ligado 23 C, GREE" })).toBe(false);
    expect(missingIrProtocol(undefined)).toBe(false);
  });
});
