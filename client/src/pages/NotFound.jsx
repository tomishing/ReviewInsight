import { Link } from "react-router-dom";
import EmptyState from "../components/EmptyState.jsx";
import { useDocumentTitle } from "../hooks.js";

export default function NotFound({ title = "Page not found", children }) {
  useDocumentTitle("Not found");
  return (
    <EmptyState title={title} action={<Link to="/apps" className="text-sm font-medium text-slate-900 underline">Go to Apps</Link>}>
      {children ?? "There is nothing at this address."}
    </EmptyState>
  );
}
