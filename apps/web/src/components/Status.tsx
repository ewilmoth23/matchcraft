import { AlertCircle, CheckCircle2, LoaderCircle, WifiOff } from 'lucide-react'

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div
      className="card flex min-h-44 items-center justify-center gap-3 p-8 text-sm text-stone-600 dark:text-stone-300"
      role="status"
    >
      <LoaderCircle className="size-5 animate-spin" aria-hidden="true" />
      {label}
    </div>
  )
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="card border-red-200 p-6 dark:border-red-900" role="alert">
      <div className="flex gap-3">
        <AlertCircle
          className="mt-0.5 size-5 shrink-0 text-red-600 dark:text-red-400"
          aria-hidden="true"
        />
        <div>
          <p className="font-semibold text-stone-900 dark:text-stone-100">Something went wrong</p>
          <p className="mt-1 text-sm text-stone-600 dark:text-stone-300">{message}</p>
          {retry && (
            <button type="button" className="btn-secondary mt-4" onClick={retry}>
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export function ProviderBadge({ status }: { status: string }) {
  const available = status === 'completed' || status === 'available'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${available ? 'bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200' : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200'}`}
    >
      {available ? <CheckCircle2 className="size-3.5" /> : <WifiOff className="size-3.5" />}
      AI {available ? 'available' : status.replaceAll('_', ' ')}
    </span>
  )
}
