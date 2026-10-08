import { create } from "zustand";
import { summaryApi } from "../api/endpoints.js";

let latest = 0; // ignore responses that arrive after a newer request

export const useSummaryStore = create((set) => ({
  data: null,
  loading: false,
  error: null,

  load: async (appId, filters) => {
    const req = ++latest;
    set({ loading: true, error: null });
    try {
      const data = await summaryApi.get(appId, filters);
      if (req === latest) set({ data, loading: false });
    } catch (e) {
      if (req === latest) set({ error: e.message, loading: false });
    }
  },

  reset: () => {
    latest++;
    set({ data: null, loading: false, error: null });
  },
}));
