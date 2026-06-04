import React, { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
}

/**
 * React Error Boundary for dashboard components.
 *
 * Catches rendering errors in child components and displays a
 * user-friendly fallback instead of crashing the entire page.
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("Dashboard ErrorBoundary caught an error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  override render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          style={{
            padding: "2rem",
            textAlign: "center",
            color: "var(--text-primary)",
            background: "var(--bg-container)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-default)",
          }}
        >
          <span
            className="material-symbols-outlined"
            style={{
              fontSize: 48,
              marginBottom: 16,
              color: "var(--error)",
            }}
          >
            error
          </span>
          <h3 style={{ marginBottom: 8 }}>Something went wrong</h3>
          <p
            style={{
              color: "var(--text-secondary)",
              fontSize: 14,
              marginBottom: 16,
            }}
          >
            This component encountered an error while rendering.
          </p>
          {this.state.error && (
            <details
              style={{
                marginTop: 16,
                textAlign: "left",
                fontSize: 12,
                color: "var(--text-tertiary)",
              }}
            >
              <summary style={{ cursor: "pointer", fontWeight: 500 }}>
                Error details
              </summary>
              <pre
                style={{
                  marginTop: 8,
                  padding: 12,
                  background: "var(--bg-base)",
                  borderRadius: "var(--radius-sm)",
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {this.state.error.name}: {this.state.error.message}
              </pre>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
