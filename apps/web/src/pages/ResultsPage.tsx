import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
  CircleDashed,
  FileJson,
  FileText,
  MessageSquareText,
  RefreshCw,
  ShieldAlert,
  Target,
  Wrench,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState, ProviderBadge } from '../components/Status'
import type { Evidence, Recommendation } from '../types/domain'

export function ResultsPage() {
  const { analysisId = '' } = useParams()
  const [search] = useSearchParams()
  const queryClient = useQueryClient()
  const started = useRef(false)
  const [exporting, setExporting] = useState<'markdown' | 'json' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const analysis = useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => api.getAnalysis(analysisId),
    enabled: Boolean(analysisId),
  })
  const run = useMutation({
    mutationFn: () => api.runAnalysis(analysisId, search.get('ai') !== '0'),
    onSuccess: (data) => {
      queryClient.setQueryData(['analysis', analysisId], data)
      // The dashboard and history list read ['analyses']; without this they kept
      // showing the pre-rerun score and state.
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
    },
  })

  // React Router reuses this component across analyses. Without a reset the run guard
  // blocks the next auto-run and, worse, the previous analysis's mutation result keeps
  // winning over the newly fetched one below.
  const resetRun = run.reset
  useEffect(() => {
    started.current = false
    resetRun()
  }, [analysisId, resetRun])

  const startRun = run.mutate
  useEffect(() => {
    if (search.get('run') === '1' && analysis.data?.state === 'ready' && !started.current) {
      started.current = true
      startRun()
    }
  }, [analysis.data?.state, startRun, search])

  if (analysis.isLoading) return <LoadingState label="Loading analysis" />
  if (analysis.isError)
    return <ErrorState message={analysis.error.message} retry={() => void analysis.refetch()} />
  if (!analysis.data) return null
  const data = run.data || analysis.data
  if (run.isPending || data.state === 'analyzing')
    return (
      <AnalysisProgress name={data.name} onRetry={run.isPending ? undefined : () => run.mutate()} />
    )
  if (!data.deterministic_complete && (run.isError || data.state === 'failed'))
    return (
      <ErrorState
        message={
          run.error?.message || data.error_message || 'Analysis failed before results were created.'
        }
        retry={() => run.mutate()}
      />
    )
  if (!data.deterministic_complete && data.state === 'ready' && search.get('run') !== '1')
    return (
      <ErrorState message="This saved analysis has not been run yet." retry={() => run.mutate()} />
    )
  if (!data.deterministic_complete && data.state === 'draft')
    return (
      <ErrorState message="Review and confirm the saved résumé before running this analysis." />
    )
  if (!data.deterministic_complete && data.state !== 'failed')
    return <LoadingState label="Preparing analysis" />

  // An unhandled rejection here meant a failed export did nothing visible at all.
  const downloadExport = (format: 'markdown' | 'json') => {
    setExportError(null)
    setExporting(format)
    api
      .downloadExport(data.id, format)
      .catch((error: unknown) =>
        setExportError(
          error instanceof Error ? error.message : 'The export could not be downloaded.',
        ),
      )
      .finally(() => setExporting(null))
  }

  const supported = data.evidence.filter((item) => item.status === 'supported')
  const missing = data.evidence.filter((item) => item.status === 'not_found')
  const transferable = data.evidence.filter((item) => item.status === 'transferable')
  const chartData = data.scores.map((score) => ({
    name: score.category.replace(' alignment', '').replace(' quality', ''),
    // A category with a zero maximum is "not scored"; dividing produced NaN%.
    percentage: score.maximum > 0 ? Math.round((score.score / score.maximum) * 100) : 0,
  }))

  return (
    <>
      <PageHeader
        eyebrow="Analysis results"
        title={data.name}
        description={`${data.target_job_title || 'Target role'}${data.target_employer ? ` at ${data.target_employer}` : ''} · updated ${new Date(data.updated_at).toLocaleDateString()}`}
        actions={
          <>
            <button
              type="button"
              className="btn-secondary"
              disabled={exporting !== null}
              onClick={() => downloadExport('markdown')}
            >
              <FileText className="size-4" aria-hidden="true" /> Markdown
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={exporting !== null}
              onClick={() => downloadExport('json')}
            >
              <FileJson className="size-4" aria-hidden="true" /> JSON
            </button>
          </>
        }
      />
      {exportError && (
        <p
          role="alert"
          className="mb-6 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
        >
          {exportError}
        </p>
      )}

      {(data.error_message || run.isError) && (
        <div
          className="mb-6 flex gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100"
          role="alert"
        >
          <AlertTriangle className="size-5 shrink-0" />
          <div>
            <p className="font-semibold">AI-assisted stage did not complete</p>
            <p className="mt-1">
              {data.error_message || run.error?.message} Deterministic results are shown where
              available.
            </p>
          </div>
        </div>
      )}
      {data.evidence.length === 0 && (
        <div
          className="mb-6 flex gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100"
          role="alert"
        >
          <AlertTriangle className="size-5 shrink-0" />
          <p>
            No explicit job requirements were detected. This report is low-confidence and its score
            mostly reflects résumé quality and non-applicable category credit.
          </p>
        </div>
      )}

      <section className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="card flex flex-col items-center justify-center p-7 text-center">
          <ScoreRing score={data.overall_score ?? 0} />
          <h2 className="mt-5 font-display text-lg font-bold">Résumé-to-role alignment</h2>
          <p className="mt-2 max-w-xs text-sm leading-6 text-stone-600 dark:text-stone-300">
            Decision-support only. This score does not predict interview or hiring outcomes.
          </p>
          <div className="mt-4">
            <ProviderBadge status={data.model_status} />
          </div>
        </div>
        <div className="card min-h-[380px] p-5 sm:p-7">
          <div className="flex items-center justify-between">
            <div>
              <p className="eyebrow">Score composition</p>
              <h2 className="mt-1 font-display text-lg font-bold">Category coverage</h2>
            </div>
            <span className="text-xs text-stone-500 dark:text-stone-400">earned / available</span>
          </div>
          {/*
            Recharts renders role="application" on its surface, which traps a screen
            reader in an unnamed widget. Every value below is duplicated as text in the
            category list, so the chart is presentational.
          */}
          <div className="mt-5 h-[290px] text-stone-600 dark:text-stone-300" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ left: 16, right: 14 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  horizontal={false}
                  stroke="currentColor"
                  strokeOpacity={0.25}
                />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                  fontSize={11}
                  tick={{ fill: 'currentColor' }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={150}
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: 'currentColor' }}
                />
                <Tooltip
                  formatter={(value) => [`${String(value)}%`, 'Coverage']}
                  cursor={{ fill: 'rgba(63,123,87,.06)' }}
                />
                <Bar dataKey="percentage" fill="#3f7b57" radius={[0, 6, 6, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-6 divide-y border-t dark:divide-stone-800 dark:border-stone-800">
            {data.scores.map((score) => (
              <article className="py-4" key={score.id}>
                <div className="flex items-start justify-between gap-4">
                  <h3 className="text-sm font-semibold">{score.category}</h3>
                  <span className="shrink-0 text-sm font-bold text-moss-800 dark:text-moss-200">
                    {score.score} / {score.maximum}
                  </span>
                </div>
                <p className="mt-1.5 text-xs leading-5 text-stone-600 dark:text-stone-300">
                  {score.reason}
                </p>
                {score.improvements.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-stone-500 dark:text-stone-400">
                    {score.improvements.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-5 lg:grid-cols-3">
        <SummaryCard
          title="Top strengths"
          icon={Check}
          items={data.result.top_strengths ?? []}
          empty="No explicit strengths detected."
          tone="success"
        />
        <SummaryCard
          title="Top gaps"
          icon={ShieldAlert}
          items={data.result.top_gaps ?? []}
          empty="No unsupported requirements detected."
          tone="warning"
        />
        <SummaryCard
          title="Transferable experience"
          icon={ArrowRight}
          items={data.result.transferable_experience ?? []}
          empty="No transferable matches detected."
          tone="neutral"
        />
      </section>

      {data.result.model_executive_summary && (
        <section className="card mt-6 border-moss-200 p-6 dark:border-moss-900">
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">Model-generated summary</p>
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:bg-amber-950 dark:text-amber-200">
              Review required
            </span>
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-7 text-stone-700 dark:text-stone-200">
            {data.result.model_executive_summary}
          </p>
          {typeof data.result.model_responsibility_alignment === 'number' && (
            <p className="mt-3 text-xs font-semibold text-stone-500 dark:text-stone-400">
              Model-assessed responsibility overlap:{' '}
              {Math.round(data.result.model_responsibility_alignment * 100)}% · explanatory only,
              not added to the deterministic score
            </p>
          )}
          {Boolean(data.result.model_transferable_experience?.length) && (
            <div className="mt-4 border-t pt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                Model-identified transferable evidence
              </p>
              <ul className="mt-2 space-y-2 text-sm text-stone-700 dark:text-stone-200">
                {data.result.model_transferable_experience?.map((item) => (
                  <li key={item}>“{item}”</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <section className="mt-8">
        <div className="mb-4">
          <p className="eyebrow">Traceability</p>
          <h2 className="mt-1 font-display text-2xl font-bold">Requirement evidence</h2>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-300">
            Supported items cite exact résumé text. “Not found” means the supplied résumé lacks
            evidence—not that you lack the ability.
          </p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <EvidenceList title={`Matched (${supported.length})`} items={supported} />
          <EvidenceList title={`Unsupported (${missing.length})`} items={missing} />
          {transferable.length > 0 && (
            <div className="lg:col-span-2">
              <EvidenceList
                title={`Potentially transferable (${transferable.length})`}
                items={transferable}
              />
            </div>
          )}
        </div>
      </section>

      <section className="mt-8">
        <div className="mb-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">Prioritized actions</p>
            <h2 className="mt-1 font-display text-2xl font-bold">Recommendations</h2>
          </div>
          <Link to={`/analyses/${data.id}/bullets`} className="btn-secondary">
            <Wrench className="size-4" /> Open bullet workshop
          </Link>
        </div>
        <div className="space-y-3">
          {data.recommendations.length ? (
            data.recommendations.map((item) => (
              <RecommendationCard key={item.id} item={item} analysisId={data.id} />
            ))
          ) : (
            <div className="card p-6 text-sm text-stone-500 dark:text-stone-400">
              No recommendations were generated.
            </div>
          )}
        </div>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-2">
        <Link
          to={`/analyses/${data.id}/bullets`}
          className="card group flex items-center gap-4 p-5 hover:border-moss-400"
        >
          <span className="grid size-11 place-items-center rounded-xl bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200">
            <Wrench className="size-5" />
          </span>
          <span className="flex-1">
            <span className="block font-display font-bold">Bullet workshop</span>
            <span className="mt-1 block text-sm text-stone-500 dark:text-stone-400">
              Create evidence-cited rewrite suggestions for review.
            </span>
          </span>
          <ChevronRight className="size-5 text-stone-400 group-hover:translate-x-1" />
        </Link>
        <Link
          to={`/analyses/${data.id}/interview`}
          className="card group flex items-center gap-4 p-5 hover:border-moss-400"
        >
          <span className="grid size-11 place-items-center rounded-xl bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200">
            <MessageSquareText className="size-5" />
          </span>
          <span className="flex-1">
            <span className="block font-display font-bold">Interview preparation</span>
            <span className="mt-1 block text-sm text-stone-500 dark:text-stone-400">
              Practice from real overlaps and gaps.
            </span>
          </span>
          <ChevronRight className="size-5 text-stone-400 group-hover:translate-x-1" />
        </Link>
      </section>

      <div className="mt-8 flex justify-center">
        <button className="btn-secondary" disabled={run.isPending} onClick={() => run.mutate()}>
          <RefreshCw className="size-4" /> Rerun analysis
        </button>
      </div>
    </>
  )
}

function AnalysisProgress({ name, onRetry }: { name: string; onRetry?: () => void }) {
  return (
    <div className="mx-auto max-w-xl pt-20 text-center" role="status">
      <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200">
        <CircleDashed className="size-8 animate-spin" />
      </span>
      <p className="eyebrow mt-6">Analysis in progress</p>
      <h1 className="mt-2 font-display text-2xl font-bold">{name}</h1>
      <p className="mt-3 text-sm leading-6 text-stone-600 dark:text-stone-300">
        Matching explicit requirements, tracing evidence, and calculating the eight score
        categories. Local AI is attempted only after deterministic analysis.
      </p>
      {onRetry && (
        <button className="btn-secondary mt-5" onClick={onRetry}>
          <RefreshCw className="size-4" /> Restart interrupted analysis
        </button>
      )}
    </div>
  )
}

function ScoreRing({ score }: { score: number }) {
  const rounded = Math.round(score)
  return (
    <div
      className="relative grid size-44 place-items-center rounded-full"
      style={{ background: `conic-gradient(#3f7b57 ${rounded * 3.6}deg, #e7e5e4 0deg)` }}
      aria-label={`${rounded} out of 100`}
    >
      <div className="grid size-36 place-items-center rounded-full bg-white dark:bg-stone-900">
        <div>
          <span className="font-display text-5xl font-bold tracking-tight">{rounded}</span>
          <span className="block text-xs font-semibold uppercase tracking-wider text-stone-500 dark:text-stone-400">
            out of 100
          </span>
        </div>
      </div>
    </div>
  )
}

function SummaryCard({
  title,
  icon: Icon,
  items,
  empty,
  tone,
}: {
  title: string
  icon: typeof Target
  items: string[]
  empty: string
  tone: 'success' | 'warning' | 'neutral'
}) {
  const style =
    tone === 'success'
      ? 'bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200'
      : tone === 'warning'
        ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200'
        : 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-200'
  return (
    <article className="card p-5">
      <div className="flex items-center gap-3">
        <span className={`grid size-9 place-items-center rounded-lg ${style}`}>
          <Icon className="size-4" />
        </span>
        <h2 className="font-display font-bold">{title}</h2>
      </div>
      <ul className="mt-4 space-y-2.5">
        {items.length ? (
          items.map((item) => (
            <li key={item} className="flex gap-2 text-sm leading-5">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-stone-400" />
              {item}
            </li>
          ))
        ) : (
          <li className="text-sm text-stone-500 dark:text-stone-400">{empty}</li>
        )}
      </ul>
    </article>
  )
}

function EvidenceList({ title, items }: { title: string; items: Evidence[] }) {
  return (
    <div className="card overflow-hidden">
      <h3 className="border-b bg-stone-50 px-5 py-3 font-display text-sm font-bold dark:bg-stone-950">
        {title}
      </h3>
      {items.length ? (
        <div className="divide-y dark:divide-stone-800">
          {items.map((item) => (
            <article key={item.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <h4 className="font-semibold">{item.requirement}</h4>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${item.status === 'supported' ? 'bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200' : item.status === 'transferable' ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200' : 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300'}`}
                >
                  {item.status.replace('_', ' ')}
                </span>
              </div>
              {item.resume_excerpt ? (
                <blockquote className="mt-3 border-l-2 border-moss-400 pl-3 text-sm italic leading-6 text-stone-600 dark:text-stone-300">
                  “{item.resume_excerpt}”
                </blockquote>
              ) : (
                <p className="mt-3 text-sm text-stone-500 dark:text-stone-400">
                  No résumé evidence found.
                </p>
              )}
              <p className="mt-2 text-xs leading-5 text-stone-500 dark:text-stone-400">
                {item.interpretation} · {item.confidence} confidence
                {item.source_section ? ` · ${item.source_section}` : ''}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <p className="p-5 text-sm text-stone-500 dark:text-stone-400">No items in this group.</p>
      )}
    </div>
  )
}

function RecommendationCard({ item, analysisId }: { item: Recommendation; analysisId: string }) {
  const queryClient = useQueryClient()
  const update = useMutation({
    mutationFn: (status: 'accepted' | 'dismissed') =>
      api.updateRecommendation(analysisId, item.id, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['analysis', analysisId] })
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
    },
  })
  return (
    <article className={`card p-5 ${item.status !== 'open' ? 'opacity-65' : ''}`}>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-600 dark:bg-stone-800 dark:text-stone-300">
              {item.priority}
            </span>
            {item.confirmation_required && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                confirmation required
              </span>
            )}
            {item.source === 'model' && (
              <span className="text-[10px] font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">
                model-generated
              </span>
            )}
          </div>
          <h3 className="mt-2 font-display text-lg font-bold">{item.title}</h3>
        </div>
        {item.status === 'open' ? (
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-lg border p-2 text-stone-500 hover:text-moss-700 disabled:opacity-50 dark:text-stone-400 dark:hover:text-moss-300"
              onClick={() => update.mutate('accepted')}
              disabled={update.isPending}
              aria-label={`Accept ${item.title}`}
            >
              <Check className="size-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              className="rounded-lg border p-2 text-stone-500 hover:text-red-600 disabled:opacity-50 dark:text-stone-400 dark:hover:text-red-400"
              onClick={() => update.mutate('dismissed')}
              disabled={update.isPending}
              aria-label={`Dismiss ${item.title}`}
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </div>
        ) : (
          <span
            role="status"
            className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400"
          >
            {item.title} {item.status}
          </span>
        )}
      </div>
      <p className="mt-3 text-sm leading-6 text-stone-600 dark:text-stone-300">
        {item.explanation}
      </p>
      {item.supporting_evidence && (
        <blockquote className="mt-3 border-l-2 border-stone-300 pl-3 text-sm italic text-stone-500 dark:text-stone-400">
          “{item.supporting_evidence}”
        </blockquote>
      )}
      <div className="mt-4 rounded-xl bg-stone-50 p-3 text-sm leading-6 dark:bg-stone-950">
        <span className="font-semibold">Recommended action: </span>
        {item.recommended_action}
      </div>
    </article>
  )
}
