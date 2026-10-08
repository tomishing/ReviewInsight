import { create } from "zustand";
import { appsApi, runsApi } from "../api/endpoints.js";

const POLL_MS = 2000;

// busy[appId] = { kind: "fetch" | "analyse", text }
// result[appId] = { ok: boolean, text } — outcome of the last action, shown in the row
export const useAppsStore = create((set, get) => ({
  apps: [],
  loading: false,
  error: null,
  busy: {},
  result: {},

  load: async () => {
    set({ loading: true, error: null });
    try {
      set({ apps: await appsApi.list(), loading: false });
    } catch (e) {
      set({ error: e.message, loading: false });
    }
  },

  refreshOne: async (id) => {
    try {
      const app = await appsApi.get(id);
      set({ apps: get().apps.map((a) => (a.id === id ? app : a)) });
    } catch {
      /* the row keeps its previous values; the next full load will catch up */
    }
  },

  create: async (body) => {
    const app = await appsApi.create(body);
    set({ apps: [...get().apps, app].sort((a, b) => a.name.localeCompare(b.name)) });
    return app;
  },

  update: async (id, body) => {
    const app = await appsApi.update(id, body);
    set({ apps: get().apps.map((a) => (a.id === id ? app : a)) });
    return app;
  },

  remove: async (id) => {
    await appsApi.remove(id);
    const { [id]: _b, ...busy } = get().busy;
    const { [id]: _r, ...result } = get().result;
    set({ apps: get().apps.filter((a) => a.id !== id), busy, result });
  },

  _setBusy: (id, value) => {
    const busy = { ...get().busy };
    if (value) busy[id] = value;
    else delete busy[id];
    set({ busy });
  },

  _setResult: (id, value) => set({ result: { ...get().result, [id]: value } }),

  fetchReviews: async (id) => {
    if (get().busy[id]) return;
    get()._setBusy(id, { kind: "fetch", text: "Fetching reviews…" });
    try {
      const r = await appsApi.fetchReviews(id);
      const errors = Object.entries(r.stores)
        .filter(([, s]) => s.error)
        .map(([store, s]) => `${store === "play" ? "Play" : "App Store"}: ${s.error}`);
      get()._setResult(id, {
        ok: r.status !== "error",
        text: [`${r.inserted} new review${r.inserted === 1 ? "" : "s"}`, ...errors].join(" · "),
      });
    } catch (e) {
      get()._setResult(id, { ok: false, text: e.message });
    } finally {
      get()._setBusy(id, null);
      get().refreshOne(id);
    }
  },

  analyse: async (id) => {
    if (get().busy[id]) return;
    const app = get().apps.find((a) => a.id === id);
    const pending = app ? app.play_reviews + app.appstore_reviews - app.analysed_reviews : 0;
    get()._setBusy(id, { kind: "analyse", text: "Starting analysis…" });

    // Poll the run log for progress while the (long) request is open.
    let stopped = false;
    const poll = async () => {
      if (stopped) return;
      try {
        const [run] = await runsApi.list(id, 1);
        if (!stopped && run?.status === "running") {
          const text =
            run.kind === "extract"
              ? `Extracting ${run.items} / ${Math.min(pending, 1000)} reviews…`
              : "Clustering themes…";
          get()._setBusy(id, { kind: "analyse", text });
        }
      } catch {
        /* progress is best-effort */
      }
      if (!stopped) timer = setTimeout(poll, POLL_MS);
    };
    let timer = setTimeout(poll, POLL_MS);

    try {
      const r = await appsApi.analyse(id);
      const parts = [];
      if (r.extract.status === "ok" || r.extract.items) parts.push(`${r.extract.items} reviews analysed`);
      if (r.cluster.status === "ok") parts.push(`${r.cluster.items} themes`);
      if (!parts.length && r.status !== "error") parts.push("Nothing new to analyse");
      const errors = [r.extract, r.cluster].filter((s) => s.status === "error").map((s) => s.error);
      get()._setResult(id, { ok: r.status !== "error", text: [...parts, ...errors].join(" · ") });
    } catch (e) {
      get()._setResult(id, { ok: false, text: e.message });
    } finally {
      stopped = true;
      clearTimeout(timer);
      get()._setBusy(id, null);
      get().refreshOne(id);
    }
  },
}));
