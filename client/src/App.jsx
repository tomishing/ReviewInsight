import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api/client.js";
import Apps from "./pages/Apps.jsx";
import AppDetail from "./pages/AppDetail.jsx";
import Compare from "./pages/Compare.jsx";

const navClass = ({ isActive }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium ${
    isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-200"
  }`;

function ApiStatus() {
  const [status, setStatus] = useState("checking");
  useEffect(() => {
    api("/api/health")
      .then(() => setStatus("ok"))
      .catch(() => setStatus("down"));
  }, []);
  const color = { checking: "bg-slate-400", ok: "bg-green-500", down: "bg-red-500" }[status];
  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-500">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      API {status}
    </span>
  );
}

export default function App() {
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
        <Routes>
          <Route path="/" element={<Navigate to="/apps" replace />} />
          <Route path="/apps" element={<Apps />} />
          <Route path="/apps/:id" element={<AppDetail />} />
          <Route path="/compare" element={<Compare />} />
        </Routes>
      </main>
    </div>
  );
}
