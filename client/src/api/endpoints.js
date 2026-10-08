import { api, download } from "./client.js";

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

export const compareApi = {
  get: (type) => api(`/api/compare${query({ type })}`),
  refresh: (type) => api(`/api/compare/refresh${query({ type })}`, { method: "POST" }),
  group: (groupId) => api(`/api/compare/groups/${groupId}`),
  groupReviews: (groupId, appId) => api(`/api/compare/groups/${groupId}/reviews${query({ app_id: appId })}`),
};

export const exportApi = {
  markdown: (appId) => download(`/api/export/markdown${query({ app_id: appId })}`),
};
