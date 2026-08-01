import React from 'react';

/**
 * React class-component error boundary. When any child component throws
 * during render, we catch it and show a helpful error card instead of a
 * completely blank page.
 *
 * Blank pages are almost impossible to diagnose from a user report. With
 * this boundary the user gets:
 *   - a visible error message with the exception type,
 *   - a "Reload" button and a "Back to dashboard" link,
 *   - the build SHA (helps distinguish stale-build vs new-code bugs),
 *   - the raw error in a <details> block for developers.
 */
class DashboardErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { error, errorInfo: null };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    // eslint-disable-next-line no-console
    console.error('DashboardErrorBoundary caught:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleBack = () => {
    // Force a hard back to the dashboard root so a stale route can recover
    window.location.href = '/dashboard';
  };

  render() {
    if (this.state.error) {
      const err = this.state.error;
      const msg = err?.message || String(err);
      const stack = this.state.errorInfo?.componentStack || err?.stack || '';
      return (
        <div className="min-h-[60vh] flex items-center justify-center p-6" data-testid="dashboard-error-boundary">
          <div className="max-w-lg w-full bg-red-500/10 border border-red-500/30 rounded-2xl p-6">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-red-400 text-xl font-bold">!</span>
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-white text-lg font-bold mb-1">Something went wrong on this page</h2>
                <p className="text-gray-400 text-sm mb-4">
                  We hit a rendering error. This is usually a stale browser cache after a fresh deploy.
                  Try a hard reload (Ctrl/Cmd + Shift + R) or go back to the dashboard.
                </p>
                <p className="text-red-300 text-xs font-mono bg-black/30 rounded p-2 mb-4 break-all">
                  {msg}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={this.handleReload}
                    data-testid="error-boundary-reload"
                    className="px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-semibold"
                  >
                    Hard Reload
                  </button>
                  <button
                    onClick={this.handleBack}
                    data-testid="error-boundary-back"
                    className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-sm font-semibold"
                  >
                    Back to Dashboard
                  </button>
                </div>
                {stack && (
                  <details className="mt-4 text-gray-500 text-xs">
                    <summary className="cursor-pointer hover:text-gray-300">Show technical details</summary>
                    <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] bg-black/40 p-2 rounded max-h-64 overflow-auto">
                      {stack}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default DashboardErrorBoundary;
