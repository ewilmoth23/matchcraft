import { useMutation } from '@tanstack/react-query'
import { CircleHelp, Cpu, Tag } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'
import type { JobDescription } from '../types/domain'

export function JobReviewPage() {
  const [search] = useSearchParams()
  const resumeId = search.get('resume') || ''
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [parsed, setParsed] = useState<JobDescription | null>(null)
  const [useModel, setUseModel] = useState(true)
  const parse = useMutation({
    mutationFn: () => (parsed ? api.updateJob(parsed.id, text) : api.createJob(text)),
    onSuccess: setParsed,
  })
  const reviewed = parsed?.raw_text === text ? parsed : null
  const proceed = useMutation({
    mutationFn: async () => {
      if (!reviewed) throw new Error('Parse and review the current job description first.')
      return api.createAnalysis(resumeId, reviewed.id)
    },
    onSuccess: (analysis) => navigate(`/analyses/${analysis.id}?run=1&ai=${useModel ? '1' : '0'}`),
  })

  const required = reviewed?.requirements.filter((item) => item.priority === 'required') ?? []
  const preferred = reviewed?.requirements.filter((item) => item.priority === 'preferred') ?? []
  const context = reviewed?.requirements.filter((item) => item.priority === 'context') ?? []
  const error = parse.error || proceed.error

  return (
    <>
      <PageHeader
        eyebrow="Step 3 of 3"
        title="Review the target role"
        description="Paste the complete job description. MatchCraft separates explicit requirements, preferences, and contextual themes before scoring."
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="card p-5 sm:p-7">
          <label htmlFor="job-text" className="text-sm font-semibold">
            Job description
          </label>
          <textarea
            id="job-text"
            className="field mt-2 min-h-[560px] resize-y text-sm leading-6"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Paste the job title, responsibilities, required qualifications, and preferred qualifications…"
          />
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-stone-600 dark:text-stone-300">
              <input
                type="checkbox"
                className="size-4 rounded accent-moss-700"
                checked={useModel}
                onChange={(event) => setUseModel(event.target.checked)}
              />{' '}
              Add local AI insights when available
            </label>
            {!reviewed ? (
              <button
                className="btn-primary"
                disabled={text.trim().length < 80 || parse.isPending}
                onClick={() => parse.mutate()}
              >
                {parse.isPending ? 'Parsing…' : 'Parse requirements'}
              </button>
            ) : (
              <button
                className="btn-primary"
                disabled={proceed.isPending}
                onClick={() => proceed.mutate()}
              >
                {proceed.isPending ? 'Preparing…' : 'Run analysis'}
              </button>
            )}
          </div>
          {error && (
            <p
              className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200"
              role="alert"
            >
              {error.message}
            </p>
          )}
        </section>

        {/*
          A live region around the whole panel made a screen reader announce every parsed
          requirement in one uninterruptible burst. The summary line below carries the
          announcement instead.
        */}
        <aside className="space-y-4" aria-label="Parsed requirements">
          <p role="status" className="sr-only">
            {reviewed
              ? `Parsed ${required.length} required, ${preferred.length} preferred, and ${context.length} contextual requirements.`
              : ''}
          </p>
          {!reviewed ? (
            <div className="card p-6">
              <CircleHelp className="size-6 text-stone-400" />
              <h2 className="mt-4 font-display text-lg font-bold">
                {parsed ? 'Text changed' : 'Nothing inferred yet'}
              </h2>
              <p className="mt-2 text-sm leading-6 text-stone-600 dark:text-stone-300">
                {parsed
                  ? 'Parse the current text again so you can review its classifications before analysis.'
                  : 'Parse the description to inspect its classification. Ambiguous language remains labeled as context rather than employer-required.'}
              </p>
            </div>
          ) : (
            <>
              <div className="card p-5">
                <p className="eyebrow">Detected role</p>
                <h2 className="mt-2 font-display text-xl font-bold">
                  {reviewed.title || 'Title not detected'}
                </h2>
                <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
                  {reviewed.employer || 'Employer not detected'}
                  {reviewed.location ? ` · ${reviewed.location}` : ''}
                </p>
              </div>
              <RequirementGroup title="Required" items={required} tone="required" />
              {required.length === 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
                  No explicit required qualifications were detected. Confirm that the complete
                  posting is present before continuing.
                </div>
              )}
              <RequirementGroup title="Preferred" items={preferred} tone="preferred" />
              <RequirementGroup title="Context & themes" items={context} tone="context" />
            </>
          )}
          <div className="rounded-2xl border border-moss-200 bg-moss-50 p-4 text-sm leading-6 text-moss-900 dark:border-moss-900 dark:bg-moss-950 dark:text-moss-100">
            <Cpu className="mr-2 inline size-4" /> AI is optional. Deterministic extraction,
            matching, scores, evidence, and exports remain available offline.
          </div>
        </aside>
      </div>
    </>
  )
}

function RequirementGroup({
  title,
  items,
  tone,
}: {
  title: string
  items: JobDescription['requirements']
  tone: 'required' | 'preferred' | 'context'
}) {
  const style =
    tone === 'required'
      ? // clay on clay/10 measured 3.11:1 at 12px, below the 4.5:1 required for body text.
        'bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-200'
      : tone === 'preferred'
        ? 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-200'
        : 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300'
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-display font-bold">{title}</h2>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${style}`}>
          {items.length}
        </span>
      </div>
      {items.length ? (
        <ul className="mt-3 space-y-2">
          {items.slice(0, 8).map((item) => (
            <li key={item.id} className="flex gap-2 text-sm leading-5">
              <Tag className="mt-0.5 size-3.5 shrink-0 text-stone-400" />
              <span>
                {item.text}
                <span className="ml-1 text-[10px] uppercase tracking-wide text-stone-600 dark:text-stone-400">
                  {item.explicitness}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">None detected.</p>
      )}
    </div>
  )
}
