import { create } from "zustand";
import { themesApi } from "../api/endpoints.js";

let latest = 0;

// The side panel listing the original reviews behind one theme.
export const useThemesStore = create((set, get) => ({
  openId: null,
  data: null,
  loading: false,
  error: null,

  open: async (themeId, filters) => {
    const req = ++latest;
    set({ openId: themeId, data: null, loading: true, error: null });
    try {
      const data = await themesApi.reviews(themeId, filters);
      if (req === latest) set({ data, loading: false });
    } catch (e) {
      if (req === latest) set({ error: e.message, loading: false });
    }
  },

  retry: (filters) => {
    const { openId } = get();
    if (openId) get().open(openId, filters);
  },

  close: () => {
    latest++;
    set({ openId: null, data: null, loading: false, error: null });
  },
}));
