import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = { readonly children: ReactNode }
type State = { readonly failed: boolean }

/**
 * Without a boundary, any render-time throw unmounts the whole tree and leaves a
 * blank page with no recovery path. Only the error type is reported: messages can
 * embed résumé or job-description values.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('MatchCraft render error', error.name, info.componentStack)
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" className="mx-auto max-w-xl px-6 py-16 text-center">
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
          Something went wrong in the interface
        </h1>
        <p className="mt-3 text-stone-600 dark:text-stone-300">
          Your saved analyses are stored locally and were not affected. Reload the page to continue.
        </p>
        <button type="button" className="btn-primary mt-6" onClick={() => window.location.reload()}>
          Reload MatchCraft
        </button>
      </div>
    )
  }
}
