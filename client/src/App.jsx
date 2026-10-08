import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api/client.js";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import Apps from "./pages/Apps.jsx";
import AppDetail from "./pages/AppDetail.jsx";
import Compare from "./pages/Compare.jsx";
import NotFound from "./pages/NotFound.jsx";

const HEALTH_POLL_MS = 30000;

const navClass = ({ isActive }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium ${
    isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-200"
  }`;

function ApiStatus() {
  const [status, setStatus] = useState("checking");
  // Re-check periodically and when the tab regains focus, so the dot follows the server.
  useEffect(() => {
    const check = () =>
      api("/api/health")
        .then(() => setStatus("ok"))
        .catch(() => setStatus("down"));
    check();
    const timer = setInterval(check, HEALTH_POLL_MS);
    window.addEventListener("focus", check);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", check);
    };
  }, []);
  const color = { checking: "bg-slate-400", ok: "bg-green-500", down: "bg-red-500" }[status];
  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-500" title={status === "down" ? "The API server is not responding — is `docker compose up` running?" : undefined}>
      <span className={`h-2 w-2 rounded-full ${color}`} />
      API {status}
    </span>
  );
}

export default function App() {
  const { pathname } = useLocation();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <span className="font-semibold">ReviewInsight</span>
          <nav className="flex gap-1">
            <NavLink to="/apps" className={navClass}>Apps</NavLink>
            <NavLink to="/compare" className={navClass}>Compare</NavLink>
          </nav>
          <div className="ml-auto"><ApiStatus /></div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <ErrorBoundary resetKey={pathname}>
          <Routes>
            <Route path="/" element={<Navigate to="/apps" replace />} />
            <Route path="/apps" element={<Apps />} />
            <Route path="/apps/:id" element={<AppDetail />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  );
}
