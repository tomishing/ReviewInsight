import { create } from "zustand";
import { compareApi } from "../api/endpoints.js";

let latest = 0;

export const useCompareStore = create((set, get) => ({
  data: null, // matrix for `type`
  type: null,
  loading: false,
  error: null,
  refreshing: false,
  refreshError: null,

  load: async (type) => {
    const req = ++latest;
    set({ type, loading: true, error: null, ...(get().type !== type && { data: null }) });
    try {
      const data = await compareApi.get(type);
      if (req === latest) set({ data, loading: false });
    } catch (e) {
      if (req === latest) set({ error: e.message, loading: false });
    }
  },

  refresh: async (type) => {
    if (get().refreshing) return;
    set({ refreshing: true, refreshError: null });
    try {
      const r = await compareApi.refresh(type);
      const failed = Object.values(r.runs).find((x) => x.status === "error");
      if (failed) set({ refreshError: failed.error });
    } catch (e) {
      set({ refreshError: e.message });
    } finally {
      set({ refreshing: false });
      if (get().type === type) get().load(type);
    }
  },
}));
