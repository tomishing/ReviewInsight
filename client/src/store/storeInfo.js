import { create } from "zustand";
import { storeInfoApi } from "../api/endpoints.js";

export const useStoreInfoStore = create((set, get) => ({
  data: null, // { country, apps: [...] }
  loading: false,
  error: null,
  refreshing: false, // true while "Refresh all" runs
  refreshError: null,
  busy: {}, // appId → true while that row refreshes

  load: async () => {
    set({ loading: true, error: null });
    try {
      set({ data: await storeInfoApi.list(), loading: false });
    } catch (e) {
      set({ error: e.message, loading: false });
    }
  },

  refreshAll: async () => {
    if (get().refreshing) return;
    set({ refreshing: true, refreshError: null });
    try {
      await storeInfoApi.refreshAll();
    } catch (e) {
      set({ refreshError: e.message });
    } finally {
      set({ refreshing: false });
      get().load();
    }
  },

  refreshOne: async (id) => {
    if (get().busy[id]) return;
    set({ busy: { ...get().busy, [id]: true } });
    try {
      const { errors: _errors, ...app } = await storeInfoApi.refresh(id);
      const data = get().data;
      if (data) set({ data: { ...data, apps: data.apps.map((a) => (a.id === id ? app : a)) } });
    } catch (e) {
      set({ refreshError: e.message });
    } finally {
      const { [id]: _b, ...busy } = get().busy;
      set({ busy });
    }
  },
}));
