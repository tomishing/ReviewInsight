import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { useAppsStore } from "../store/apps.js";
import AppFormModal from "../components/AppFormModal.jsx";
import EmptyState from "../components/EmptyState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const ago = (iso) => (iso ? formatDistanceToNow(new Date(iso), { addSuffix: true }) : "never");

const btn =
  "rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40";

function AppRow({ app, onEdit }) {
  const { busy, result, fetchReviews, analyse, remove } = useAppsStore();
  const b = busy[app.id];
  const r = result[app.id];
  const total = app.play_reviews + app.appstore_reviews;
  const run = app.last_run;

  const onDelete = async () => {
    if (!window.confirm(`Delete ${app.name} and all its reviews and analysis?`)) return;
    try {
      await remove(app.id);
    } catch (e) {
      window.alert(e.message);
    }
  };

  return (
    <tr className="border-t border-slate-100 align-top">
      <td className="px-4 py-3">
        <Link to={`/apps/${app.id}`} className="font-medium text-slate-900 hover:underline">
          {app.name}
        </Link>
        <div className="mt-0.5 space-x-2 text-xs text-slate-500">
          {app.play_id && <span title="Google Play ID">Play {app.play_id}</span>}
          {app.appstore_id && <span title="App Store ID">iOS {app.appstore_id}</span>}
        </div>
        {app.notes && <div className="mt-0.5 text-xs text-slate-400">{app.notes}</div>}
      </td>
      <td className="px-4 py-3 text-right tabular-nums">
        <div>{total.toLocaleString()}</div>
        <div className="text-xs text-slate-500">
          {app.play_id && <>Play {app.play_reviews.toLocaleString()}</>}
          {app.play_id && app.appstore_id && " · "}
          {app.appstore_id && <>iOS {app.appstore_reviews.toLocaleString()}</>}
        </div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">
        {app.analysed_reviews.toLocaleString()}
        {total > 0 && <div className="text-xs text-slate-500">{Math.round((app.analysed_reviews / total) * 100)}%</div>}
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        <div>Fetched {ago(app.last_fetched_at)}</div>
        {run && (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
            {run.kind} <StatusBadge status={run.status} title={run.error} /> {ago(run.finished_at || run.started_at)}
          </div>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap justify-end gap-1.5">
          <button className={btn} disabled={!!b} onClick={() => fetchReviews(app.id)}>Fetch</button>
          <button
            className={btn}
            disabled={!!b || total === 0}
            title={total === 0 ? "Fetch reviews first" : undefined}
            onClick={() => analyse(app.id)}
          >
            Analyse
          </button>
          <button className={btn} disabled={!!b} onClick={() => onEdit(app)}>Edit</button>
          <button className={`${btn} text-red-700`} disabled={!!b} onClick={onDelete}>Delete</button>
        </div>
        <div className="mt-2 max-w-xs text-right text-xs" aria-live="polite">
          {b ? (
            <span className="inline-flex items-center gap-1.5 text-slate-600">
              <LoadingSpinner size="sm" label="" /> {b.text}
            </span>
          ) : (
            r && <span className={r.ok ? "text-slate-600" : "text-red-700"}>{r.ok ? "✓ " : "✕ "}{r.text}</span>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function Apps() {
  const { apps, loading, error, load, create, update } = useAppsStore();
  const [editing, setEditing] = useState(undefined); // undefined = closed, null = new, app = edit

  useEffect(() => {
    load();
  }, [load]);

  const save = (form) => (editing ? update(editing.id, form) : create(form));

  let body;
  if (loading && !apps.length) body = <div className="py-16"><LoadingSpinner label="Loading apps…" /></div>;
  else if (error && !apps.length) body = <ErrorState title="Couldn't load apps" message={error} onRetry={load} />;
  else if (!apps.length)
    body = (
      <EmptyState
        title="No apps yet"
        action={<button onClick={() => setEditing(null)} className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white">Add an app</button>}
      >
        Add a competitor with its Google Play and/or App Store ID, then fetch and analyse its reviews.
      </EmptyState>
    );
  else
    body = (
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">App</th>
              <th className="px-4 py-2 text-right">Reviews</th>
              <th className="px-4 py-2 text-right">Analysed</th>
              <th className="px-4 py-2">Last activity</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {apps.map((a) => <AppRow key={a.id} app={a} onEdit={setEditing} />)}
          </tbody>
        </table>
      </div>
    );

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Apps</h1>
          <p className="text-sm text-slate-500">Competitor apps whose reviews are tracked.</p>
        </div>
        {apps.length > 0 && (
          <button onClick={() => setEditing(null)} className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700">
            Add app
          </button>
        )}
      </div>
      {error && apps.length > 0 && (
        <div className="mb-3"><ErrorState title="Couldn't refresh apps" message={error} onRetry={load} /></div>
      )}
      {body}
      {editing !== undefined && <AppFormModal app={editing} onSave={save} onClose={() => setEditing(undefined)} />}
    </section>
  );
}
