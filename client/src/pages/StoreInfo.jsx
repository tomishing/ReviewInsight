import { useEffect } from "react";
import { Link } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { useStoreInfoStore } from "../store/storeInfo.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import { useDocumentTitle } from "../hooks.js";

const ago = (iso) => (iso ? formatDistanceToNow(new Date(iso), { addSuffix: true }) : "never");
const dash = <span className="text-slate-400">—</span>;

const btn =
  "rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40";

// One store's rating cell: rating, count, installs (Play), link, last error.
function StoreCell({ id, info, label }) {
  if (!id) return <td className="px-4 py-3 text-xs text-slate-400">Not on {label}</td>;
  const d = info?.data;
  return (
    <td className="px-4 py-3">
      {d?.rating != null ? (
        <div className="tabular-nums">
          <span className="font-medium">{d.rating.toFixed(1)}</span> <span className="text-amber-500">★</span>
        </div>
      ) : (
        <div>{dash}</div>
      )}
      <div className="text-xs text-slate-500 tabular-nums">
        {d?.rating_count != null && <div>{d.rating_count.toLocaleString()} ratings</div>}
        {d?.installs && <div>{d.installs} installs</div>}
        {d?.url && (
          <a href={d.url} target="_blank" rel="noreferrer" className="hover:underline">
            Store page ↗
          </a>
        )}
      </div>
      {info?.error && <div className="mt-1 max-w-[14rem] text-xs text-red-700">{info.error}</div>}
    </td>
  );
}

function PriceCell({ app }) {
  const play = app.play?.data;
  const ios = app.appstore?.data;
  const { plans } = app.revenue_model;
  const downloadPrice = [play, ios].find((d) => d?.price > 0);
  const planList = [
    plans.monthly && `${plans.monthly} / month`,
    plans.yearly && `${plans.yearly} / year`,
    plans.lifetime && `${plans.lifetime} lifetime`,
  ].filter(Boolean);
  const items = ios?.iap_items || [];

  if (!play && !ios) return <td className="px-4 py-3">{dash}</td>;
  return (
    <td className="px-4 py-3">
      {downloadPrice && (
        <div className="font-medium">
          {downloadPrice.price.toFixed(2)} {downloadPrice.currency} to download
        </div>
      )}
      {planList.length > 0 ? (
        <div className="space-y-0.5 tabular-nums">{planList.map((p) => <div key={p}>{p}</div>)}</div>
      ) : (
        !downloadPrice && !app.revenue_model.in_app_purchases && <div>Free</div>
      )}
      {play?.iap_range && (
        <div className="mt-1 text-xs text-slate-500" title="Google Play only gives the range of its in-app prices">
          Play: {play.iap_range}
        </div>
      )}
      {items.length > 0 && (
        <details className="mt-1 text-xs text-slate-500">
          <summary className="cursor-pointer hover:text-slate-700">
            App Store in-app purchases ({items.length})
          </summary>
          <ul className="mt-1 space-y-0.5">
            {items.map((i) => (
              <li key={`${i.name}|${i.price}`} className="flex justify-between gap-3">
                <span>{i.name}</span>
                <span className="tabular-nums">{i.price}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </td>
  );
}

function Row({ app }) {
  const { busy, refreshing, refreshOne } = useStoreInfoStore();
  const fetched = [app.play?.fetched_at, app.appstore?.fetched_at].filter(Boolean).sort()[0];
  return (
    <tr className="border-t border-slate-100 align-top">
      <td className="px-4 py-3">
        <Link to={`/apps/${app.id}`} className="font-medium text-slate-900 hover:underline">
          {app.name}
        </Link>
      </td>
      <StoreCell id={app.play_id} info={app.play} label="Google Play" />
      <StoreCell id={app.appstore_id} info={app.appstore} label="App Store" />
      <td className="px-4 py-3">{app.revenue_model.label ?? dash}</td>
      <PriceCell app={app} />
      <td className="px-4 py-3 text-right text-xs text-slate-500">
        <div>{ago(fetched)}</div>
        <button className={`${btn} mt-1.5`} disabled={busy[app.id] || refreshing} onClick={() => refreshOne(app.id)}>
          {busy[app.id] ? "Refreshing…" : "Refresh"}
        </button>
      </td>
    </tr>
  );
}

export default function StoreInfo() {
  useDocumentTitle("Store info");
  const { data, loading, error, refreshing, refreshError, load, refreshAll } = useStoreInfoStore();

  useEffect(() => {
    load();
  }, [load]);

  const apps = data?.apps || [];
  const neverFetched = apps.length > 0 && apps.every((a) => !a.play && !a.appstore);
  const currency = apps.map((a) => a.play?.data?.currency || a.appstore?.data?.currency).find(Boolean);

  let body;
  if (loading && !data) body = <div className="py-16"><LoadingSpinner label="Loading store info…" /></div>;
  else if (error && !data) body = <ErrorState title="Couldn't load store info" message={error} onRetry={load} />;
  else if (!apps.length)
    body = (
      <EmptyState title="No apps yet" action={<Link to="/apps" className="text-sm font-medium underline">Go to Apps</Link>}>
        Add competitor apps first; their store details then show here.
      </EmptyState>
    );
  else if (neverFetched)
    body = (
      <EmptyState
        title="No store details yet"
        action={
          <button onClick={refreshAll} disabled={refreshing} className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
            {refreshing ? "Fetching…" : "Fetch store details"}
          </button>
        }
      >
        Reads each app's rating, price and in-app purchases from Google Play and the App Store (about 2 s per app).
      </EmptyState>
    );
  else
    body = (
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[960px] text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">App</th>
              <th className="px-4 py-2">Google Play</th>
              <th className="px-4 py-2">App Store</th>
              <th className="px-4 py-2">Revenue model</th>
              <th className="px-4 py-2">Price</th>
              <th className="px-4 py-2 text-right">Updated</th>
            </tr>
          </thead>
          <tbody>
            {apps.map((a) => <Row key={a.id} app={a} />)}
          </tbody>
        </table>
      </div>
    );

  return (
    <section>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Store info</h1>
          <p className="text-sm text-slate-500">
            Ratings, revenue model and prices from the {(data?.country || "").toUpperCase()} stores
            {currency && <> (prices in {currency}, as listed)</>}. Monthly / yearly / lifetime prices come from
            App Store purchase names; Google Play only gives a price range.
          </p>
        </div>
        {apps.length > 0 && !neverFetched && (
          <button
            onClick={refreshAll}
            disabled={refreshing}
            className="flex shrink-0 items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {refreshing && <LoadingSpinner size="sm" label="" />}
            {refreshing ? "Refreshing…" : "Refresh all"}
          </button>
        )}
      </div>
      {refreshError && <div className="mb-3"><ErrorState title="Refresh failed" message={refreshError} /></div>}
      {error && data && <div className="mb-3"><ErrorState title="Couldn't reload store info" message={error} onRetry={load} /></div>}
      {body}
    </section>
  );
}
