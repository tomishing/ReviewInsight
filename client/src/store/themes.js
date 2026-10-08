import { create } from "zustand";
import { compareApi, themesApi } from "../api/endpoints.js";

let latest = 0;

// The side panel listing original reviews: behind one app theme, or one comparison cell.
export const useThemesStore = create((set, get) => ({
  openId: null, // any key identifying what is shown
  data: null,
  loading: false,
  error: null,
  _loader: null,

  _show: async (key, loader) => {
    const req = ++latest;
    set({ openId: key, data: null, loading: true, error: null, _loader: loader });
    try {
      const data = await loader();
      if (req === latest) set({ data, loading: false });
    } catch (e) {
      if (req === latest) set({ error: e.message, loading: false });
    }
  },

  open: (themeId, filters) => get()._show(`theme:${themeId}`, () => themesApi.reviews(themeId, filters)),

  openGroup: (groupId, appId) =>
    get()._show(`group:${groupId}:${appId}`, () => compareApi.groupReviews(groupId, appId)),

  retry: () => {
    const { openId, _loader } = get();
    if (openId && _loader) get()._show(openId, _loader);
  },

  close: () => {
    latest++;
    set({ openId: null, data: null, loading: false, error: null, _loader: null });
  },
}));
