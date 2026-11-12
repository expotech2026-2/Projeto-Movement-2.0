import { apiConfig } from "../config/api";

const SESSION_KEY = "movement.operator.session";

export function getSessionToken() {
  try {
    return sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

async function failure(response, token) {
  if (response.status === 401 && token) {
    clearSession();
    window.dispatchEvent(new Event("movement:session-expired"));
  }
  const data = await response.json().catch(() => null);
  const detail =
    typeof data?.detail === "string"
      ? data.detail
      : "Confira os campos informados";
  return new Error(
    response.status === 401
      ? "Usuário, senha ou sessão inválidos"
      : `${detail} (HTTP ${response.status})`,
  );
}

export async function request(
  path,
  { token = getSessionToken(), ...options } = {},
) {
  const response = await fetch(`${apiConfig.baseUrl}${path}`, {
    ...options,
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) throw await failure(response, token);
  return response.status === 204 ? null : response.json();
}

export async function login(username, password) {
  const result = await request("/auth/login", {
    method: "POST",
    token: null,
    body: JSON.stringify({ username, password }),
  });
  sessionStorage.setItem(SESSION_KEY, result.access_token);
  return result.user;
}

export async function fetchReport(scope = {}) {
  const token = getSessionToken();
  const query = new URLSearchParams(
    Object.entries(scope).filter(([, value]) => value),
  ).toString();
  const response = await fetch(
    `${apiConfig.baseUrl}/reports/pdf${query ? `?${query}` : ""}`,
    {
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );
  if (!response.ok) throw await failure(response, token);
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename =
    /filename="([^"]+)"/.exec(disposition)?.[1] || "movement-relatorio.pdf";
  return { blob: await response.blob(), filename };
}

const catalogCache = new Map();

export function catalog(path) {
  if (!catalogCache.has(path)) {
    catalogCache.set(
      path,
      request(path).catch((error) => {
        catalogCache.delete(path);
        throw error;
      }),
    );
  }
  return catalogCache.get(path);
}

const IBGE_CITIES_URL =
  "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado&orderBy=nome";
let citiesCache = null;

// O IBGE recusa conexões de fora do Brasil e a API roda nos EUA, então o navegador busca direto.
export function cities() {
  citiesCache ??= fetch(IBGE_CITIES_URL, { signal: AbortSignal.timeout(15_000) })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`IBGE indisponível (HTTP ${response.status})`);
      }
      return response.json();
    })
    .then((list) =>
      list.map((item) => ({
        id: item["municipio-id"],
        name: item["municipio-nome"],
        state: item["UF-sigla"],
      })),
    )
    .catch((error) => {
      citiesCache = null;
      throw error;
    });
  return citiesCache;
}

export function samplingPlan(roomId, budgetRatio = 0.5) {
  return request(
    `/rooms/${encodeURIComponent(roomId)}/sampling-plan?budget_ratio=${budgetRatio}`,
  );
}

export function roomAlerts(roomId, limit = 5) {
  return request(`/rooms/${encodeURIComponent(roomId)}/alerts?limit=${limit}`);
}

export function roomControl(roomId) {
  return request(`/rooms/${encodeURIComponent(roomId)}/control`);
}

export function setRoomControl(roomId, command) {
  return request(`/rooms/${encodeURIComponent(roomId)}/control`, {
    method: "PUT",
    body: JSON.stringify(command),
  });
}

export function sendIrProtocol(roomId) {
  return request(`/rooms/${encodeURIComponent(roomId)}/ir-protocol`, {
    method: "POST",
  });
}

export function regenerateDeviceToken(roomId, deviceId) {
  return request(
    `/rooms/${encodeURIComponent(roomId)}/devices/${encodeURIComponent(deviceId)}/token`,
    { method: "POST" },
  );
}
