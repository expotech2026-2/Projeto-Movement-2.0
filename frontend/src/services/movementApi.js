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
  if (!response.ok) {
    if (response.status === 401 && token) {
      clearSession();
      window.dispatchEvent(new Event("movement:session-expired"));
    }
    const data = await response.json().catch(() => null);
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : "Confira os campos informados";
    throw new Error(
      response.status === 401
        ? "Usuário, senha ou sessão inválidos"
        : `${detail} (HTTP ${response.status})`,
    );
  }
  return response.status === 204 ? null : response.json();
}

export async function login(username, password) {
  const result = await request("/auth/login", {
    method: "POST",
    token: null,
    body: JSON.stringify({ username, password }),
  });
  sessionStorage.setItem(SESSION_KEY, result.access_token);
}
