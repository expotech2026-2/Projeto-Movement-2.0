import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  catalog,
  cities,
  clearSession,
  fetchReport,
  getSessionToken,
  irTransport,
  login,
  regenerateDeviceToken,
  request,
  roomAlerts,
  roomControl,
  samplingPlan,
  setRoomControl,
  setIrTransport,
  sendIrProtocol,
} from "./movementApi";
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
      new Response(
        JSON.stringify({
          access_token: "test-session",
          user: { username: "admin", role: "admin" },
        }),
        { status: 200 },
      ),
    );
    await expect(login("admin", "test-password")).resolves.toEqual({
      username: "admin",
      role: "admin",
    });
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

  it("baixa o relatório PDF com a sessão e o nome enviado pela API", async () => {
    storage.set("movement.operator.session", "valid-token");
    fetch.mockResolvedValue(
      new Response(new Blob(["%PDF-1.4"]), {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition":
            'attachment; filename="movement-relatorio-20261104-1130.pdf"',
        },
      }),
    );
    const report = await fetchReport({ unit_id: "unidade-1", room_id: "" });
    expect(report.filename).toBe("movement-relatorio-20261104-1130.pdf");
    expect(await report.blob.text()).toBe("%PDF-1.4");
    expect(fetch).toHaveBeenLastCalledWith(
      `${apiConfig.baseUrl}/reports/pdf?unit_id=unidade-1`,
      expect.objectContaining({
        headers: { Authorization: "Bearer valid-token" },
      }),
    );
  });

  it("consulta o plano de leitura com o orçamento escolhido", async () => {
    fetch.mockResolvedValueOnce(
      new Response('{"hours":[],"energy_j":0}', { status: 200 }),
    );
    await expect(samplingPlan("sala-1", 0.3)).resolves.toEqual({
      hours: [],
      energy_j: 0,
    });
    expect(fetch).toHaveBeenLastCalledWith(
      `${apiConfig.baseUrl}/rooms/sala-1/sampling-plan?budget_ratio=0.3`,
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("consulta os alertas recentes da sala", async () => {
    fetch.mockResolvedValueOnce(new Response("[]", { status: 200 }));
    await expect(roomAlerts("sala 1")).resolves.toEqual([]);
    expect(fetch).toHaveBeenLastCalledWith(
      `${apiConfig.baseUrl}/rooms/sala%201/alerts?limit=5`,
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("busca os municípios direto no IBGE, sem a sessão, e reaproveita a lista", async () => {
    storage.set("movement.operator.session", "valid-token");
    const ibge = [
      {
        "municipio-id": 3509502,
        "municipio-nome": "Campinas",
        "UF-sigla": "SP",
      },
    ];
    fetch
      .mockResolvedValueOnce(new Response("{}", { status: 503 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(ibge), { status: 200 }),
      );
    await expect(cities()).rejects.toThrow("HTTP 503");
    const list = [{ id: 3509502, name: "Campinas", state: "SP" }];
    await expect(cities()).resolves.toEqual(list);
    await expect(cities()).resolves.toEqual(list);
    expect(fetch).toHaveBeenCalledTimes(2);
    const [url, options] = fetch.mock.lastCall;
    expect(url).toBe(
      "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado&orderBy=nome",
    );
    expect(options.headers).toBeUndefined();
  });

  it("consulta o comando do ar-condicionado da sala", async () => {
    const control = { mode: "auto", target: null, version: 0, outside: null };
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(control), { status: 200 }),
    );
    await expect(roomControl("sala 1")).resolves.toEqual(control);
    expect(fetch).toHaveBeenLastCalledWith(
      `${apiConfig.baseUrl}/rooms/sala%201/control`,
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("envia o comando manual do professor com PUT", async () => {
    fetch.mockResolvedValueOnce(
      new Response('{"mode":"manual","target":21,"version":1}', {
        status: 200,
      }),
    );
    await expect(
      setRoomControl("sala-1", { mode: "manual", target: 21 }),
    ).resolves.toEqual({ mode: "manual", target: 21, version: 1 });
    expect(fetch).toHaveBeenLastCalledWith(
      `${apiConfig.baseUrl}/rooms/sala-1/control`,
      expect.objectContaining({
        method: "PUT",
        body: '{"mode":"manual","target":21}',
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("consulta e salva o emissor por sala", async () => {
    const configuration = {
      transport: "xiaomi",
      gateway_url: "http://10.0.0.4:8080/ac",
    };
    fetch.mockResolvedValue(
      new Response(JSON.stringify({ ...configuration, revision: 2 }), {
        status: 200,
      }),
    );
    await irTransport("sala /1");
    expect(fetch.mock.lastCall[0]).toBe(
      `${apiConfig.baseUrl}/rooms/sala%20%2F1/ir-transport`,
    );
    fetch.mockResolvedValue(
      new Response(JSON.stringify({ ...configuration, revision: 2 }), {
        status: 200,
      }),
    );
    await setIrTransport("sala /1", configuration);
    expect(fetch).toHaveBeenLastCalledWith(
      `${apiConfig.baseUrl}/rooms/sala%20%2F1/ir-transport`,
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify(configuration),
      }),
    );
  });

  it("gera um novo token para o dispositivo da sala com POST", async () => {
    fetch.mockResolvedValueOnce(
      new Response('{"id":"esp32-1","room_id":"sala 1","token":"novo"}', {
        status: 200,
      }),
    );
    await expect(regenerateDeviceToken("sala 1", "esp32-1")).resolves.toEqual({
      id: "esp32-1",
      room_id: "sala 1",
      token: "novo",
    });
    expect(fetch).toHaveBeenLastCalledWith(
      `${apiConfig.baseUrl}/rooms/sala%201/devices/esp32-1/token`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("reaproveita consultas ao catálogo e repete após falha", async () => {
    fetch
      .mockResolvedValueOnce(new Response("{}", { status: 500 }))
      .mockResolvedValueOnce(new Response('[{"brand":"LG"}]', { status: 200 }));
    await expect(catalog("/catalog/brands")).rejects.toThrow("HTTP 500");
    await expect(catalog("/catalog/brands")).resolves.toEqual([
      { brand: "LG" },
    ]);
    await expect(catalog("/catalog/brands")).resolves.toEqual([
      { brand: "LG" },
    ]);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe("Envio de protocolo IR", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("prepara o protocolo da sala pelo endpoint autenticado", async () => {
    vi.stubGlobal("sessionStorage", { getItem: () => "test-session" });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ revision: 1, protocols: "SAMSUNG_AC:1" }),
            { status: 200 },
          ),
        ),
    );
    await expect(sendIrProtocol("sala /1")).resolves.toEqual({
      revision: 1,
      protocols: "SAMSUNG_AC:1",
    });
    expect(fetch).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/rooms/sala%20%2F1/ir-protocol`,
      expect.objectContaining({
        method: "POST",
        headers: { Authorization: "Bearer test-session" },
      }),
    );
  });
});
