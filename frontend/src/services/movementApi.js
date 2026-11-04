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
