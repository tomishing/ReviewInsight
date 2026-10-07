const API_URL = import.meta.env.VITE_API_URL || "http://localhost:4000";

// Unwraps the { data, error } envelope; throws on error.
export async function api(path, { body, headers, ...options } = {}) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: body !== undefined ? { "Content-Type": "application/json", ...headers } : headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error(`Cannot reach the API at ${API_URL}`);
  }
  const json = await res.json().catch(() => null);
  if (!res.ok || json?.error) {
    throw new Error(json?.error || `Request failed (${res.status})`);
  }
  return json?.data ?? null;
}
