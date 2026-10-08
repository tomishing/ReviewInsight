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

// Downloads a file endpoint (non-JSON on success; { data, error } on failure).
export async function download(path) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`);
  } catch {
    throw new Error(`Cannot reach the API at ${API_URL}`);
  }
  if (!res.ok) {
    const json = await res.json().catch(() => null);
    throw new Error(json?.error || `Download failed (${res.status})`);
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "export.md";
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return name;
}
