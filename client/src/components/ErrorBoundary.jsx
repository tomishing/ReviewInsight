import { Component } from "react";

// Catches render errors so a bug shows a message instead of a blank page.
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidUpdate(prev) {
    // Navigating elsewhere (new resetKey) gives the page another chance.
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm">
        <p className="font-medium text-red-800">This page hit an unexpected error.</p>
        <p className="mt-1 break-words font-mono text-xs text-red-700">{String(this.state.error.message || this.state.error)}</p>
        <button onClick={() => window.location.reload()} className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1.5 font-medium text-red-800 hover:bg-red-100">
          Reload
        </button>
      </div>
    );
  }
}
