// Talks to the PromptDock REST API on the same origin. The user's name (X-Actor) and the
// optional server token are kept in this browser only.

const ACTOR_KEY = "promptdock.actor";
const TOKEN_KEY = "promptdock.token";

export const settings = {
  get actor() {
    return localStorage.getItem(ACTOR_KEY) || "";
  },
  get token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  },
  save(actor, token) {
    localStorage.setItem(ACTOR_KEY, actor.trim());
    if (token.trim()) localStorage.setItem(TOKEN_KEY, token.trim());
    else localStorage.removeItem(TOKEN_KEY);
  },
};

export class ApiError extends Error {
  constructor(status, body) {
    const error = body?.error;
    super(error?.message || `Request failed (${status})`);
    this.status = status;
    this.type = error?.type;
    this.failures = error?.failures || [];
  }
}

// Listeners called when the server says a token is needed (401).
const unauthorizedListeners = new Set();
export function onUnauthorized(fn) {
  unauthorizedListeners.add(fn);
  return () => unauthorizedListeners.delete(fn);
}

export async function api(path, { method = "GET", body, params } = {}) {
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null) url.searchParams.set(key, value);
  }
  const headers = { Accept: "application/json" };
  if (settings.token) headers.Authorization = `Bearer ${settings.token}`;
  if (settings.actor) headers["X-Actor"] = encodeURIComponent(settings.actor);
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (response.status === 401) unauthorizedListeners.forEach((fn) => fn());
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

export const p = (name) => `/prompts/${encodeURIComponent(name)}`;
