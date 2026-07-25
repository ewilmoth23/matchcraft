import { useQuery } from '@tanstack/react-query'
import { ArrowRight, FileCheck2, LockKeyhole, Plus, Target } from 'lucide-react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState, ProviderBadge } from '../components/Status'

export function DashboardPage() {
  const analyses = useQuery({ queryKey: ['analyses'], queryFn: api.listAnalyses })
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })

  return (
    <>
      <PageHeader
        eyebrow="Local workspace"
        title="Know what your résumé proves."
        description="Compare a résumé with a specific role using transparent scoring, traceable evidence, and recommendations bounded by review and evidence checks."
        actions={
          <Link className="btn-primary" to="/analyses/new">
            <Plus className="size-4" /> New analysis
          </Link>
        }
      />

      <section className="grid gap-4 md:grid-cols-3" aria-label="Product principles">
        {[
          [
            Target,
            'Evidence-grounded',
            'Every match points to a résumé excerpt. Every gap is clearly marked as not found.',
          ],
          [
            FileCheck2,
            'Transparent scoring',
            'Eight visible categories explain exactly how the alignment score is composed.',
          ],
          [
            LockKeyhole,
            'Private by default',
            'Deterministic analysis works with AI disabled and documents remain in local storage.',
          ],
        ].map(([Icon, title, copy]) => {
          const FeatureIcon = Icon as typeof Target
          return (
            <article className="card p-5" key={String(title)}>
              <span className="grid size-10 place-items-center rounded-xl bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200">
                <FeatureIcon className="size-5" />
              </span>
              <h2 className="mt-4 font-display text-base font-bold">{String(title)}</h2>
              <p className="mt-1.5 text-sm leading-6 text-stone-600 dark:text-stone-300">
                {String(copy)}
              </p>
            </article>
          )
        })}
      </section>

      <section className="mt-8">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="eyebrow">Recent work</p>
            <h2 className="mt-1 font-display text-xl font-bold">Analyses</h2>
          </div>
          {health.data && <ProviderBadge status={health.data.ai_features} />}
        </div>
        {analyses.isLoading && <LoadingState label="Loading analyses" />}
        {analyses.isError && (
          <ErrorState message={analyses.error.message} retry={() => void analyses.refetch()} />
        )}
        {analyses.data?.length === 0 && (
          <div className="card flex flex-col items-center px-6 py-14 text-center">
            <span className="grid size-12 place-items-center rounded-2xl bg-stone-100 dark:bg-stone-800">
              <Target className="size-6 text-stone-500 dark:text-stone-400" />
            </span>
            <h3 className="mt-4 font-display text-lg font-bold">No analyses yet</h3>
            <p className="mt-2 max-w-md text-sm leading-6 text-stone-600 dark:text-stone-300">
              Start with résumé text or a PDF/DOCX. You will review every extracted word before
              analysis.
            </p>
            <Link to="/analyses/new" className="btn-primary mt-5">
              Create your first analysis
            </Link>
          </div>
        )}
        {!!analyses.data?.length && (
          <div className="card divide-y divide-stone-200 overflow-hidden dark:divide-stone-800">
            {analyses.data.slice(0, 5).map((analysis) => (
              <Link
                key={analysis.id}
                to={`/analyses/${analysis.id}`}
                className="group flex items-center gap-4 p-4 transition-colors hover:bg-stone-50 dark:hover:bg-stone-800/60 sm:p-5"
              >
                <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-moss-50 font-display text-sm font-bold text-moss-800 dark:bg-moss-950 dark:text-moss-200">
                  {analysis.overall_score == null ? '—' : Math.round(analysis.overall_score)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{analysis.name}</span>
                  <span className="mt-1 block text-xs text-stone-500 dark:text-stone-400">
                    {new Date(analysis.updated_at).toLocaleDateString()} · {analysis.state}
                  </span>
                </span>
                <ArrowRight className="size-4 text-stone-400 transition-transform group-hover:translate-x-1" />
              </Link>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
