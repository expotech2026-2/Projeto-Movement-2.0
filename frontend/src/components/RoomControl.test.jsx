import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RoomControl } from "./RoomControl";

const state = { control: { mode: "auto" }, loading: false, send: () => {} };
const missing = { ac_state: "sem protocolo IR (rode IR_TESTE)", online: true };

describe("Botão de protocolo na visão geral", () => {
  it("aparece ao administrador quando o ESP32 está sem protocolo", () => {
    const html = renderToStaticMarkup(
      createElement(RoomControl, { state, device: missing, isAdmin: true }),
    );
    expect(html).toContain("Enviar protocolo para o ESP32");
  });

  it("não aparece quando o ESP32 já possui protocolo nem para professor", () => {
    for (const props of [
      { device: { ac_state: "desligado, SAMSUNG_AC" }, isAdmin: true },
      { device: missing, isAdmin: false },
    ]) {
      const html = renderToStaticMarkup(
        createElement(RoomControl, { state, ...props }),
      );
      expect(html).not.toContain("Enviar protocolo para o ESP32");
    }
  });
});
