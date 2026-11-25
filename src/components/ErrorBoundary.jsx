import React from 'react';
import { reportError } from '../lib/errorReporter';

// A page crash shows a calm "something went wrong" card instead of a blank
// white screen, and is logged for Admin → Errors.
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // After a deploy an open tab can ask for a page file that no longer exists.
    // Reload once to pick up the new version instead of showing an error.
    const msg = String(error?.message || '');
    if (/dynamically imported module|Loading chunk|Importing a module script failed/i.test(msg)) {
      try {
        if (!sessionStorage.getItem('laro_chunk_reload')) {
          sessionStorage.setItem('laro_chunk_reload', '1');
          window.location.reload();
          return;
        }
      } catch {
        /* ignore */
      }
    }
    reportError(error, { componentStack: info?.componentStack });
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-cream-subtle">
        <div className="max-w-sm w-full bg-white dark:bg-card rounded-2xl border border-border/60 p-6 text-center space-y-4">
          <h1 className="font-heading text-xl font-semibold">Something went wrong</h1>
          <p className="text-sm text-muted-foreground">
            This page hit a problem. It has been logged so it can be fixed. Your recipes are safe.
          </p>
          <div className="flex gap-2 justify-center">
            <button
              type="button"
              className="rounded-full bg-laro text-white px-4 py-2 text-sm font-medium"
              onClick={() => window.location.reload()}
            >
              Reload
            </button>
            <button
              type="button"
              className="rounded-full border border-border px-4 py-2 text-sm font-medium"
              onClick={() => {
                window.location.hash = '#/';
                window.location.reload();
              }}
            >
              Go home
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
