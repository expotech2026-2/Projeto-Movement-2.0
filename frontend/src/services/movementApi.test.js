import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearSession, getSessionToken, login, request } from "./movementApi";
import { apiConfig } from "../config/api";

describe("API Movement", () => {
  let storage;
  let events;
  beforeEach(() => {
    storage = new Map();
    events = new EventTarget();
    vi.stubGlobal("sessionStorage", {
      getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    });
    vi.stubGlobal("window", events);
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it("armazena a sessão e envia autorização nas próximas requisições", async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ access_token: "test-session" }), {
        status: 200,
      }),
    );
    await login("admin", "test-password");
    expect(getSessionToken()).toBe("test-session");
    fetch.mockResolvedValueOnce(new Response("[]", { status: 200 }));
    await request("/rooms");
    expect(fetch).toHaveBeenLastCalledWith(
      `${apiConfig.baseUrl}/rooms`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-session",
        }),
        cache: "no-store",
      }),
    );
    clearSession();
    expect(getSessionToken()).toBeNull();
  });

  it("expira a sessão e notifica a interface ao receber HTTP 401", async () => {
    storage.set("movement.operator.session", "expired-token");
    const listener = vi.fn();
    events.addEventListener("movement:session-expired", listener);
    fetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Sessão inválida" }), {
        status: 401,
      }),
    );
    await expect(request("/rooms")).rejects.toThrow("sessão inválidos");
    expect(listener).toHaveBeenCalledOnce();
    expect(getSessionToken()).toBeNull();
  });

  it("trata exclusões HTTP 204 sem tentar interpretar JSON vazio", async () => {
    fetch.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(
      request("/rooms/empty", { method: "DELETE" }),
    ).resolves.toBeNull();
  });

  it("exibe conflitos de vínculo sem encerrar uma sessão válida", async () => {
    storage.set("movement.operator.session", "valid-token");
    fetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Registro vinculado" }), {
        status: 409,
      }),
    );
    await expect(request("/rooms/used", { method: "DELETE" })).rejects.toThrow(
      "Registro vinculado",
    );
    expect(getSessionToken()).toBe("valid-token");
  });

  it("converte erros de validação em mensagem legível", async () => {
    fetch.mockResolvedValue(
      new Response(
        JSON.stringify({ detail: [{ loc: ["body", "capacity"] }] }),
        { status: 422 },
      ),
    );
    await expect(request("/rooms")).rejects.toThrow("Confira os campos");
  });
});
