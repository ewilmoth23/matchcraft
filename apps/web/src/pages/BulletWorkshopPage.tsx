import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Check, Clipboard, LockKeyhole, Wrench } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/Status'

export function BulletWorkshopPage() {
  const { analysisId = '' } = useParams()
  const analysis = useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => api.getAnalysis(analysisId),
    enabled: Boolean(analysisId),
  })
  const resume = useQuery({
    queryKey: ['resume', analysis.data?.resume_id],
    queryFn: () => api.getResume(analysis.data!.resume_id),
    enabled: Boolean(analysis.data?.resume_id),
  })
  const bullets = useMemo(() => {
    if (resume.data?.structured_data.bullets?.length) return resume.data.structured_data.bullets
    return (
      resume.data?.extracted_text
        .split('\n')
        .filter((line) => /^[•*\-–—]\s+/.test(line.trim()))
        .map((line) => line.trim().replace(/^[•*\-–—]\s+/, '')) ?? []
    )
  }, [resume.data])
  const [selected, setSelected] = useState('')
  const [copied, setCopied] = useState(false)
  const rewrite = useMutation({
    mutationFn: (bullet: string) => api.rewriteBullet(analysisId, bullet),
  })
  const current = selected || bullets[0] || ''
  const diagnostics = analysis.data?.result.bullet_analysis?.find(
    (item) => item.original_bullet === current,
  )

  if (analysis.isLoading || resume.isLoading)
    return <LoadingState label="Loading bullet workshop" />
  if (analysis.isError) return <ErrorState message={analysis.error.message} />
  if (resume.isError) return <ErrorState message={resume.error.message} />

  return (
    <>
      <PageHeader
        eyebrow="Fact-preserving workspace"
        title="Bullet workshop"
        description="Improve clarity without changing job titles, dates, tools, metrics, scope, or outcomes. Unknown facts stay visible as placeholders."
        actions={
          <Link className="btn-secondary" to={`/analyses/${analysisId}`}>
            <ArrowLeft className="size-4" /> Results
          </Link>
        }
      />
      <div
        className="mb-6 flex gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100"
        role="alert"
      >
        <AlertTriangle className="mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-semibold">Non-fabrication boundary</p>
          <p>
            Review every suggestion. Replace bracketed values only with facts you can verify;
            otherwise remove the placeholder. MatchCraft never treats a suggestion as approved
            résumé content.
          </p>
        </div>
      </div>
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="card overflow-hidden">
          <div className="border-b p-5">
            <h2 className="font-display font-bold">Résumé bullets</h2>
            <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">
              Choose the exact source statement to revise.
            </p>
          </div>
          {bullets.length ? (
            <div className="max-h-[680px] divide-y overflow-y-auto dark:divide-stone-800">
              {bullets.map((bullet, index) => (
                <button
                  type="button"
                  key={`${index}-${bullet}`}
                  // Selection was conveyed by background colour alone (WCAG 1.4.1).
                  aria-pressed={current === bullet}
                  onClick={() => {
                    setSelected(bullet)
                    rewrite.reset()
                    setCopied(false)
                  }}
                  className={`w-full p-4 text-left text-sm leading-6 transition-colors ${current === bullet ? 'bg-moss-50 text-moss-950 dark:bg-moss-950 dark:text-moss-100' : 'hover:bg-stone-50 dark:hover:bg-stone-800'}`}
                >
                  <span className="mr-2 text-xs font-bold text-stone-600 dark:text-stone-400">
                    {index + 1}
                  </span>
                  {bullet}
                </button>
              ))}
            </div>
          ) : (
            <p className="p-5 text-sm text-stone-500 dark:text-stone-400">
              No bulleted lines were detected in the reviewed résumé text.
            </p>
          )}
        </section>

        <section className="space-y-5">
          <div className="card p-5 sm:p-7">
            <p className="eyebrow">Original bullet</p>
            <p className="mt-3 text-base leading-7">{current || 'Select a résumé bullet.'}</p>
            {diagnostics && (
              <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Diagnostic
                  label="Action"
                  value={diagnostics.action_led ? diagnostics.action_verb || 'Yes' : 'Needs review'}
                />
                <Diagnostic label="Clarity" value={diagnostics.task_clarity} />
                <Diagnostic
                  label="Metric"
                  value={diagnostics.measurable_outcome ? 'Detected' : 'Not detected'}
                />
                <Diagnostic
                  label="Role overlap"
                  value={`${Math.round(diagnostics.job_relevance * 100)}%`}
                />
                <Diagnostic label="Length" value={`${diagnostics.length_words} words`} />
                <Diagnostic
                  label="Impact"
                  value={diagnostics.business_impact ? 'Detected' : 'Not detected'}
                />
                <Diagnostic
                  label="Technical detail"
                  value={diagnostics.technical_detail.join(', ') || 'Not detected'}
                />
                <Diagnostic
                  label="Repetition"
                  value={diagnostics.redundant_phrases.length ? 'Review' : 'None detected'}
                />
              </dl>
            )}
            <button
              className="btn-primary mt-5"
              disabled={!current || rewrite.isPending}
              onClick={() => rewrite.mutate(current)}
            >
              <Wrench className="size-4" />
              {rewrite.isPending ? 'Generating…' : 'Generate safe rewrite'}
            </button>
            {rewrite.isError && (
              <p className="mt-3 text-sm text-red-600 dark:text-red-400" role="alert">
                {rewrite.error.message}
              </p>
            )}
          </div>
          {rewrite.data ? (
            <div className="card border-moss-200 p-5 sm:p-7 dark:border-moss-900">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="eyebrow">Suggested wording</p>
                  <div className="mt-2 flex gap-2">
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                      confirmation required
                    </span>
                    {rewrite.data.model_generated && (
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-800 dark:bg-blue-950 dark:text-blue-200">
                        model-generated
                      </span>
                    )}
                  </div>
                </div>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    void navigator.clipboard.writeText(rewrite.data.suggested_bullet)
                    setCopied(true)
                  }}
                >
                  {copied ? <Check className="size-4" /> : <Clipboard className="size-4" />}
                  {copied ? 'Copied' : 'Copy suggestion'}
                </button>
              </div>
              <p className="mt-5 rounded-xl bg-moss-50 p-4 text-base leading-7 text-moss-950 dark:bg-moss-950 dark:text-moss-100">
                {rewrite.data.suggested_bullet}
              </p>
              <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="font-semibold">Why it changed</dt>
                  <dd className="mt-1 leading-6 text-stone-600 dark:text-stone-300">
                    {rewrite.data.reason}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold">Factual source</dt>
                  <dd className="mt-1 leading-6 text-stone-600 dark:text-stone-300">
                    {rewrite.data.factual_sources.join(' · ')}
                  </dd>
                </div>
              </dl>
              <p className="mt-5 flex gap-2 border-t pt-4 text-xs leading-5 text-stone-500 dark:text-stone-400">
                <LockKeyhole className="mt-0.5 size-3.5 shrink-0" />
                {rewrite.data.warning}
              </p>
            </div>
          ) : (
            <div className="card border-dashed p-8 text-center text-sm text-stone-500 dark:text-stone-400">
              A rewrite, its factual source, rationale, and confirmation marker will appear here.
            </div>
          )}
        </section>
      </div>
    </>
  )
}

function Diagnostic({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-stone-50 p-2.5 dark:bg-stone-950">
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
        {label}
      </dt>
      <dd className="mt-1 truncate text-xs font-semibold capitalize" title={value}>
        {value}
      </dd>
    </div>
  )
}
