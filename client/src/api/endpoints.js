import { api } from "./client.js";

// Builds "?a=1&b=2" from an object, skipping empty values.
function query(params = {}) {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ).toString();
  return q ? `?${q}` : "";
}

export const appsApi = {
  list: () => api("/api/apps"),
  get: (id) => api(`/api/apps/${id}`),
  create: (body) => api("/api/apps", { method: "POST", body }),
  update: (id, body) => api(`/api/apps/${id}`, { method: "PUT", body }),
  remove: (id) => api(`/api/apps/${id}`, { method: "DELETE" }),
  fetchReviews: (id, body) => api(`/api/apps/${id}/fetch`, { method: "POST", body }),
  analyse: (id, body) => api(`/api/apps/${id}/analyse`, { method: "POST", body }),
};

export const runsApi = {
  list: (appId, limit = 10) => api(`/api/runs${query({ app_id: appId, limit })}`),
};

export const summaryApi = {
  get: (appId, filters) => api(`/api/apps/${appId}/summary${query(filters)}`),
};

export const themesApi = {
  reviews: (themeId, filters) => api(`/api/themes/${themeId}/reviews${query(filters)}`),
};
