/**
 * Centralized HTTP client for the FIN_BOT API.
 *
 * - Reads base URL from VITE_FINBOT_API_URL and strips trailing slashes.
 * - Injects `Authorization: Bearer <token>` on every call.
 * - On HTTP 401 tries to refresh the session ONCE, then retries the original
 *   request. If refresh fails, the session is cleared and the user is
 *   redirected to /login.
 * - On HTTP 403 exposes a typed ApiError so the UI can render an access
 *   denied state and redirect the user to their allowed dashboard.
 *
 * Refresh endpoint contract (assumed):
 *   POST /api/v1/auth/refresh  { refresh_token }  -> { access_token, refresh_token? }
 * Adjust `refreshTokens` if the backend contract differs.
 */
import type { ApiErrorShape } from "@/types/api";

const RAW_URL = import.meta.env.VITE_FINBOT_API_URL ?? "";
export const API_URL = RAW_URL.replace(/\/+$/, "");
const API_PREFIX = "/api/v1";
const REQUEST_TIMEOUT_MS = 10_000;

const ACCESS_KEY = "finbot.access_token";
const REFRESH_KEY = "finbot.refresh_token";
const REMEMBER_KEY = "finbot.remember_session";

// LocalTunnel occasionally injects an interstitial page; sending this header
// tells it to skip the browser warning for cross-origin requests.
const EXTRA_HEADERS: Record<string, string> = {};
if (/\.loca\.lt(?::|\/|$)/.test(API_URL)) {
  EXTRA_HEADERS["Bypass-Tunnel-Reminder"] = "true";
}

export class ApiError extends Error implements ApiErrorShape {
  status: number;
  request_id?: string;
  detail?: unknown;
  constructor(
    status: number,
    message: string,
    opts: { request_id?: string; detail?: unknown } = {},
  ) {
    super(message);
    this.status = status;
    this.request_id = opts.request_id;
    this.detail = opts.detail;
  }
}

export const tokenStorage = {
  getAccess: () => sessionStorage.getItem(ACCESS_KEY) ?? localStorage.getItem(ACCESS_KEY),
  getRefresh: () => sessionStorage.getItem(REFRESH_KEY) ?? localStorage.getItem(REFRESH_KEY),
  setRemember(remember: boolean) {
    localStorage.setItem(REMEMBER_KEY, String(remember));
  },
  set(access: string, refresh?: string) {
    const storage = localStorage.getItem(REMEMBER_KEY) === "true" ? localStorage : sessionStorage;
    storage.setItem(ACCESS_KEY, access);
    if (refresh) storage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(REMEMBER_KEY);
  },
};

type Options = Omit<RequestInit, "body"> & {
  body?: unknown;
  auth?: boolean;
  query?: Record<string, string | number | boolean | undefined | null>;
  raw?: boolean;
  signal?: AbortSignal;
};

let refreshPromise: Promise<string | null> | null = null;
type Listener = (event: "session-expired") => void;
const listeners = new Set<Listener>();
export const onAuthEvent = (fn: Listener) => {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
};
const emit = (event: "session-expired") => listeners.forEach((fn) => fn(event));

async function refreshTokens(): Promise<string | null> {
  const refresh = tokenStorage.getRefresh();
  if (!refresh) return null;
  try {
    const res = await fetchWithTimeout(`${API_URL}${API_PREFIX}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...EXTRA_HEADERS },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return null;
    const data = (await safeJson(res)) as { access_token: string; refresh_token?: string };
    if (!data.access_token) return null;
    tokenStorage.set(data.access_token, data.refresh_token ?? refresh);
    return data.access_token;
  } catch {
    return null;
  }
}

function buildUrl(path: string, query?: Options["query"]) {
  if (!API_URL) throw new ApiError(0, "VITE_FINBOT_API_URL não configurada.");
  const full = path.startsWith("/api/")
    ? `${API_URL}${path}`
    : `${API_URL}${API_PREFIX}${path.startsWith("/") ? path : `/${path}`}`;
  if (!query) return full;
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    usp.append(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `${full}?${qs}` : full;
}

async function parseError(res: Response): Promise<ApiError> {
  const request_id = res.headers.get("x-request-id") ?? undefined;
  let message = `Erro ${res.status}`;
  let detail: unknown;
  try {
    const data = (await res.json()) as { message?: string; detail?: unknown; error?: string };
    if (typeof data.detail === "string") message = data.detail;
    else if (data.message) message = data.message;
    else if (data.error) message = data.error;
    detail = data.detail ?? data;
  } catch {
    // ignore
  }
  return new ApiError(res.status, message, { request_id, detail });
}

async function coreRequest<T>(path: string, opts: Options = {}): Promise<T> {
  const { body, auth = true, query, raw, signal, headers, ...rest } = opts;
  const url = buildUrl(path, query);
  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...EXTRA_HEADERS,
    ...(headers as Record<string, string> | undefined),
  };
  if (body !== undefined && !(body instanceof FormData)) {
    finalHeaders["Content-Type"] = "application/json";
  }
  if (auth) {
    const token = tokenStorage.getAccess();
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  }
  const init: RequestInit = {
    ...rest,
    headers: finalHeaders,
    signal,
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
  };
  const res = await fetchWithTimeout(url, init, signal);
  if (res.status === 401 && auth) {
    if (!refreshPromise)
      refreshPromise = refreshTokens().finally(() => {
        refreshPromise = null;
      });
    const newToken = await refreshPromise;
    if (!newToken) {
      tokenStorage.clear();
      emit("session-expired");
      throw await parseError(res);
    }
    finalHeaders["Authorization"] = `Bearer ${newToken}`;
    const retry = await fetchWithTimeout(url, { ...init, headers: finalHeaders }, signal);
    if (!retry.ok) throw await parseError(retry);
    return raw ? ((await retry.blob()) as unknown as T) : ((await safeJson(retry)) as T);
  }
  if (!res.ok) throw await parseError(res);
  return raw ? ((await res.blob()) as unknown as T) : ((await safeJson(res)) as T);
}

async function safeJson(res: Response) {
  if (res.status === 204) return undefined;
  const text = await res.text();
  if (!text) return undefined;
  try {
    const parsed = JSON.parse(text) as unknown;
    if (parsed && typeof parsed === "object" && "success" in parsed && "data" in parsed) {
      return (parsed as { data: unknown }).data;
    }
    return parsed;
  } catch {
    return text;
  }
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  externalSignal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort("timeout"), REQUEST_TIMEOUT_MS);
  const cancel = () => controller.abort(externalSignal?.reason ?? "cancelled");
  externalSignal?.addEventListener("abort", cancel, { once: true });
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (externalSignal?.aborted) {
      throw new ApiError(0, "Requisição cancelada.");
    }
    if (controller.signal.aborted) {
      throw new ApiError(0, "A API demorou para responder. Tente novamente.");
    }
    throw new ApiError(0, "Não foi possível conectar à API. Verifique sua rede.", {
      detail: error,
    });
  } finally {
    window.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", cancel);
  }
}

export const api = {
  get: <T>(path: string, opts?: Options) => coreRequest<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, body?: unknown, opts?: Options) =>
    coreRequest<T>(path, { ...opts, method: "POST", body }),
  put: <T>(path: string, body?: unknown, opts?: Options) =>
    coreRequest<T>(path, { ...opts, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, opts?: Options) =>
    coreRequest<T>(path, { ...opts, method: "PATCH", body }),
  delete: <T>(path: string, opts?: Options) => coreRequest<T>(path, { ...opts, method: "DELETE" }),
};
