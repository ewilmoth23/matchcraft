import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Cloud, Cpu, HardDrive, Server } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState, ProviderBadge } from '../components/Status'
import type { AppSettings } from '../types/domain'

export function SettingsPage() {
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.getSettings })
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const [form, setForm] = useState<Partial<AppSettings>>({})
  const [dirty, setDirty] = useState(false)
  // Re-seeding on every new settings reference silently discarded whatever the user
  // had typed, so the form only adopts server values while it is pristine.
  useEffect(() => {
    if (settings.data && !dirty) setForm(settings.data)
  }, [settings.data, dirty])
  const save = useMutation({
    mutationFn: () => api.updateSettings(form),
    onSuccess: (data) => {
      setDirty(false)
      setForm(data)
      queryClient.setQueryData(['settings'], data)
      void queryClient.invalidateQueries({ queryKey: ['health'] })
    },
  })
  const set = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setDirty(true)
    // Clear the "Saved" confirmation; it otherwise stayed visible over edited values.
    if (save.isSuccess || save.isError) save.reset()
    setForm((current) => ({ ...current, [key]: value }))
  }
  if (settings.isLoading) return <LoadingState label="Loading settings" />
  if (settings.isError) return <ErrorState message={settings.error.message} />
  return (
    <>
      <PageHeader
        eyebrow="Local configuration"
        title="Settings"
        description="AI runs locally first. A configured remote model is used only when local inference is unavailable or its output fails validation. Deterministic analysis never requires AI."
        actions={health.data && <ProviderBadge status={health.data.ai_features} />}
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <form
          className="card p-5 sm:p-7"
          onSubmit={(event) => {
            event.preventDefault()
            save.mutate()
          }}
        >
          <div className="flex items-center gap-3 border-b pb-5">
            <span className="grid size-10 place-items-center rounded-xl bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200">
              <Server className="size-5" />
            </span>
            <div>
              <h2 className="font-display text-lg font-bold">Model provider</h2>
              <p className="text-xs text-stone-500 dark:text-stone-400">
                Used only for labeled AI-assisted features
              </p>
            </div>
          </div>
          <div className="mt-6">
            <label className="text-sm font-semibold">
              Provider strategy
              <select
                className="field mt-2"
                value={form.provider || 'local_first'}
                onChange={(event) => set('provider', event.target.value as AppSettings['provider'])}
              >
                <option value="local_first">Local first, remote fallback (recommended)</option>
                <option value="ollama">Ollama only (local)</option>
                <option value="openai_compatible">Remote endpoint only</option>
                <option value="disabled">Disabled</option>
              </select>
            </label>
          </div>
          {(form.provider === 'local_first' || form.provider === 'ollama') && (
            <section className="mt-6 rounded-2xl border border-stone-200 p-4 dark:border-stone-700">
              <div className="flex items-center gap-2">
                <Cpu className="size-4 text-moss-700 dark:text-moss-300" />
                <h3 className="font-display font-bold">Local AI — first choice</h3>
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-semibold">
                  Ollama model
                  <input
                    className="field mt-2"
                    value={form.local_model || ''}
                    onChange={(event) => set('local_model', event.target.value)}
                    required
                  />
                </label>
                <label className="text-sm font-semibold">
                  Ollama URL
                  <input
                    className="field mt-2"
                    type="url"
                    value={form.local_provider_url || ''}
                    onChange={(event) => set('local_provider_url', event.target.value)}
                    required
                  />
                </label>
                <label className="text-sm font-semibold sm:col-span-2">
                  Local context window (tokens)
                  <input
                    className="field mt-2"
                    type="number"
                    min="4096"
                    max="131072"
                    step="1024"
                    value={form.ollama_context_tokens ?? 32768}
                    onChange={(event) => set('ollama_context_tokens', Number(event.target.value))}
                  />
                  <span className="mt-1 block text-xs font-normal text-stone-500 dark:text-stone-400">
                    32K is the recommended balance for typical résumés and job descriptions.
                  </span>
                </label>
              </div>
            </section>
          )}
          {(form.provider === 'local_first' || form.provider === 'openai_compatible') && (
            <section className="mt-5 rounded-2xl border border-stone-200 p-4 dark:border-stone-700">
              <div className="flex items-center gap-2">
                <Cloud className="size-4 text-moss-700 dark:text-moss-300" />
                <h3 className="font-display font-bold">
                  Remote AI {form.provider === 'local_first' ? '— fallback only' : ''}
                </h3>
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-semibold">
                  Remote model
                  <input
                    className="field mt-2"
                    value={form.remote_model || ''}
                    onChange={(event) => set('remote_model', event.target.value)}
                    required
                  />
                </label>
                <label className="text-sm font-semibold">
                  Reasoning effort
                  <select
                    className="field mt-2"
                    value={form.openai_reasoning_effort || 'low'}
                    onChange={(event) =>
                      set(
                        'openai_reasoning_effort',
                        event.target.value as AppSettings['openai_reasoning_effort'],
                      )
                    }
                  >
                    <option value="none">None — fastest</option>
                    <option value="low">Low — recommended</option>
                    <option value="medium">Medium — deeper</option>
                    <option value="high">High — slowest</option>
                  </select>
                </label>
                <label className="text-sm font-semibold sm:col-span-2">
                  OpenAI-compatible URL
                  <input
                    className="field mt-2"
                    type="url"
                    value={form.remote_provider_url || ''}
                    onChange={(event) => set('remote_provider_url', event.target.value)}
                    required
                  />
                </label>
              </div>
              <p className="mt-3 text-xs text-stone-500 dark:text-stone-400">
                API key:{' '}
                {form.remote_api_key_configured ? 'configured on the server' : 'not configured'}.
                Set MATCHCRAFT_OPENAI_API_KEY in the API environment; keys are never saved here.
              </p>
            </section>
          )}
          {form.provider !== 'disabled' && (
            <section className="mt-5 grid gap-5 rounded-2xl border border-stone-200 p-4 sm:grid-cols-2 dark:border-stone-700">
              <label className="text-sm font-semibold">
                Local temperature{' '}
                <span className="font-normal text-stone-500 dark:text-stone-400">
                  ({form.model_temperature})
                </span>
                <input
                  className="mt-3 w-full accent-moss-700"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={form.model_temperature ?? 0}
                  onChange={(event) => set('model_temperature', Number(event.target.value))}
                />
              </label>
              <label className="text-sm font-semibold">
                Timeout (seconds)
                <input
                  className="field mt-2"
                  type="number"
                  min="1"
                  max="300"
                  value={form.model_timeout_seconds ?? 180}
                  onChange={(event) => set('model_timeout_seconds', Number(event.target.value))}
                />
              </label>
              <label className="text-sm font-semibold">
                Maximum output tokens
                <input
                  className="field mt-2"
                  type="number"
                  min="256"
                  max="16000"
                  value={form.model_max_tokens ?? 3000}
                  onChange={(event) => set('model_max_tokens', Number(event.target.value))}
                />
              </label>
              <label className="text-sm font-semibold">
                Validation retries
                <input
                  className="field mt-2"
                  type="number"
                  min="0"
                  max="3"
                  value={form.model_retries ?? 1}
                  onChange={(event) => set('model_retries', Number(event.target.value))}
                />
              </label>
            </section>
          )}
          {(form.provider === 'openai_compatible' || form.remote_provider_warning) && (
            <div className="mt-5 flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              If local AI fails, résumé and job-description text will be sent to the configured
              remote endpoint. Remote output still passes the same evidence and fabrication checks.
            </div>
          )}
          <div className="mt-6 flex items-center justify-end gap-3">
            <span role="status" className="sr-only">
              {save.isSuccess ? 'Settings saved.' : ''}
            </span>
            {save.isSuccess && (
              <span
                aria-hidden="true"
                className="inline-flex items-center gap-1 text-sm text-moss-700 dark:text-moss-300"
              >
                <CheckCircle2 className="size-4" /> Saved
              </span>
            )}
            <button className="btn-primary" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save settings'}
            </button>
          </div>
          {save.isError && (
            <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">
              {save.error.message}
            </p>
          )}
        </form>
        <aside className="space-y-4">
          <div className="card p-5">
            <HardDrive className="size-5 text-moss-700 dark:text-moss-300" />
            <h2 className="mt-3 font-display font-bold">Local data</h2>
            <dl className="mt-3 space-y-3 text-sm">
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                  Directory
                </dt>
                <dd className="mt-1 break-all font-mono text-xs">{settings.data?.data_dir}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                  Upload limit
                </dt>
                <dd className="mt-1">
                  {Math.round((settings.data?.max_upload_bytes ?? 0) / 1024 / 1024)} MB
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                  Database
                </dt>
                <dd className="mt-1">{health.data?.database || 'Checking…'}</dd>
              </div>
            </dl>
          </div>
          <div className="card p-5">
            <h2 className="font-display font-bold">Feature availability</h2>
            <ul className="mt-3 space-y-2 text-sm text-stone-600 dark:text-stone-300">
              <li>✓ Parsing and extraction</li>
              <li>✓ Deterministic scores</li>
              <li>✓ Evidence and exports</li>
              <li>
                {health.data?.ai_features === 'available' ? '✓' : '—'} Semantic insights and model
                rewrites
              </li>
            </ul>
            {(health.data?.provider_checks.length ?? 0) > 0 && (
              <ul className="mt-4 space-y-2 border-t border-stone-200 pt-4 text-sm dark:border-stone-700">
                {health.data?.provider_checks.map((check) => (
                  <li key={check.provider} className="flex items-start justify-between gap-3">
                    <span>
                      {check.local ? 'Local' : 'Remote'} · {check.model}
                    </span>
                    <span
                      className={
                        check.status === 'available'
                          ? 'text-moss-700 dark:text-moss-300'
                          : 'text-stone-500 dark:text-stone-400'
                      }
                    >
                      {check.status.replace('_', ' ')}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </>
  )
}
