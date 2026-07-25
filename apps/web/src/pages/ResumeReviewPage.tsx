import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, FileSearch, TextCursorInput } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/Status'

export function ResumeReviewPage() {
  const { resumeId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const resume = useQuery({
    queryKey: ['resume', resumeId],
    queryFn: () => api.getResume(resumeId),
    enabled: Boolean(resumeId),
  })
  const [text, setText] = useState('')

  useEffect(() => {
    if (resume.data) setText(resume.data.extracted_text)
  }, [resume.data])

  const save = useMutation({
    mutationFn: async () => {
      if (text !== resume.data?.extracted_text) await api.updateResume(resumeId, text)
      return api.confirmResume(resumeId)
    },
    onSuccess: (confirmedResume) => {
      queryClient.setQueryData(['resume', resumeId], confirmedResume)
      void navigate(`/jobs/review?resume=${resumeId}`)
    },
  })

  if (resume.isLoading) return <LoadingState label="Loading extracted résumé" />
  if (resume.isError)
    return <ErrorState message={resume.error.message} retry={() => void resume.refetch()} />
  if (!resume.data) return null

  const words = text.trim() ? text.trim().split(/\s+/).length : 0
  return (
    <>
      <PageHeader
        eyebrow="Step 2 of 3"
        title="Review the extraction"
        description="This editable text is the only résumé evidence MatchCraft will analyze. Correct missing characters, reading order, or section breaks now."
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="card p-5 sm:p-7">
          {resume.data.extraction_warnings.map((warning) => (
            <div
              key={warning}
              role="alert"
              className="mb-4 flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100"
            >
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              {warning}
            </div>
          ))}
          <label htmlFor="extracted-text" className="text-sm font-semibold">
            Extracted résumé text
          </label>
          <textarea
            id="extracted-text"
            className="field mt-2 min-h-[620px] resize-y font-mono text-[13px] leading-6"
            value={text}
            onChange={(event) => setText(event.target.value)}
            aria-describedby="review-help"
          />
          <div className="mt-3 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <p id="review-help" className="text-xs text-stone-500 dark:text-stone-400">
              {words.toLocaleString()} words · edits do not change the original uploaded file
            </p>
            <button
              className="btn-primary"
              disabled={text.trim().length < 50 || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? (
                'Saving…'
              ) : (
                <>
                  <Check className="size-4" /> Confirm and continue
                </>
              )}
            </button>
          </div>
          {save.isError && (
            <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">
              {save.error.message}
            </p>
          )}
        </div>
        <aside className="space-y-4">
          <div className="card p-5">
            <FileSearch className="size-5 text-moss-700 dark:text-moss-300" />
            <h2 className="mt-3 font-display font-bold">What to check</h2>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-stone-600 dark:text-stone-300">
              <li>• Employment dates and employer names</li>
              <li>• Bullets split across columns</li>
              <li>• Skills and certification spelling</li>
              <li>• Missing text from tables or sidebars</li>
            </ul>
          </div>
          <div className="card p-5">
            <TextCursorInput className="size-5 text-moss-700 dark:text-moss-300" />
            <h2 className="mt-3 font-display font-bold">Fact boundary</h2>
            <p className="mt-2 text-sm leading-6 text-stone-600 dark:text-stone-300">
              Fix extraction mistakes, but do not add target-role keywords unless they truthfully
              describe your background.
            </p>
          </div>
        </aside>
      </div>
    </>
  )
}
