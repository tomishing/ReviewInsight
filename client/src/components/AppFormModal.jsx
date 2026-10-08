import { useEffect, useRef, useState } from "react";

const EMPTY = { name: "", play_id: "", appstore_id: "", notes: "" };

// Add / edit an app. `app` null = add.
export default function AppFormModal({ app, onSave, onClose }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const firstField = useRef(null);

  useEffect(() => {
    setForm(app ? { ...EMPTY, ...Object.fromEntries(Object.keys(EMPTY).map((k) => [k, app[k] ?? ""])) } : EMPTY);
    setError(null);
    firstField.current?.focus();
  }, [app]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && !saving && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, saving]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return setError("Name is required.");
    if (!form.play_id.trim() && !form.appstore_id.trim())
      return setError("Give at least a Play ID or an App Store ID.");
    setSaving(true);
    setError(null);
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  const field = "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none";
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 p-4" onMouseDown={() => !saving && onClose()}>
      <form
        onSubmit={submit}
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl"
        aria-labelledby="app-form-title"
      >
        <h2 id="app-form-title" className="text-lg font-semibold">{app ? "Edit app" : "Add app"}</h2>
        <label className="mt-4 block text-sm font-medium text-slate-700">
          Name
          <input ref={firstField} className={field} value={form.name} onChange={set("name")} />
        </label>
        <label className="mt-3 block text-sm font-medium text-slate-700">
          Google Play ID
          <input className={field} value={form.play_id} onChange={set("play_id")} placeholder="com.example.app" />
        </label>
        <label className="mt-3 block text-sm font-medium text-slate-700">
          App Store ID
          <input className={field} value={form.appstore_id} onChange={set("appstore_id")} placeholder="1459319842" inputMode="numeric" />
        </label>
        <label className="mt-3 block text-sm font-medium text-slate-700">
          Notes
          <textarea className={field} rows={2} value={form.notes} onChange={set("notes")} />
        </label>
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={saving} className="rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50">
            {saving ? "Saving…" : app ? "Save" : "Add app"}
          </button>
        </div>
      </form>
    </div>
  );
}
