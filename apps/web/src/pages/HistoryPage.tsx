import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Calendar, ExternalLink, Pencil, Plus, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/Status'

export function HistoryPage() {
  const queryClient = useQueryClient()
  const analyses = useQuery({ queryKey: ['analyses'], queryFn: api.listAnalyses })
  const [renaming, setRenaming] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const rename = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => api.renameAnalysis(id, value),
    onSuccess: (updatedAnalysis) => {
      queryClient.setQueryData(['analysis', updatedAnalysis.id], updatedAnalysis)
      setRenaming(null)
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
    },
  })
  // Deleting unmounts the trigger button, which dropped focus to <body> and told a
  // screen-reader user nothing about what happened.
  const [statusMessage, setStatusMessage] = useState('')
  const headingRef = useRef<HTMLHeadingElement>(null)
  const remove = useMutation({
    mutationFn: api.deleteAnalysis,
    onSuccess: (_data, id) => {
      const deleted = analyses.data?.find((item) => item.id === id)
      setDeleting(null)
      setStatusMessage(`Deleted ${deleted?.name ?? 'the analysis'} and its local source data.`)
      // Deferred past this commit: closing a modal <dialog> restores focus to the
      // element that opened it, which would immediately override this.
      requestAnimationFrame(() => headingRef.current?.focus())
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
    },
  })

  if (analyses.isLoading) return <LoadingState label="Loading analysis history" />
  if (analyses.isError)
    return <ErrorState message={analyses.error.message} retry={() => void analyses.refetch()} />
  return (
    <>
      <p role="status" className="sr-only">
        {statusMessage}
      </p>
      <PageHeader
        headingRef={headingRef}
        eyebrow="Local history"
        title="Saved analyses"
        description="Reopen, rename, export, or permanently delete a résumé-to-role analysis and its unshared local source data."
        actions={
          <Link className="btn-primary" to="/analyses/new">
            <Plus className="size-4" /> New analysis
          </Link>
        }
      />
      {!analyses.data?.length ? (
        <div className="card p-10 text-center">
          <h2 className="font-display text-lg font-bold">Nothing saved yet</h2>
          <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">
            Completed and draft analyses will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {analyses.data.map((analysis) => (
            <article
              className="card flex flex-col gap-4 p-5 sm:flex-row sm:items-center"
              key={analysis.id}
            >
              <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-moss-50 text-center dark:bg-moss-950">
                <span className="font-display text-lg font-bold text-moss-800 dark:text-moss-200">
                  {analysis.overall_score == null ? '—' : Math.round(analysis.overall_score)}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                {renaming === analysis.id ? (
                  <form
                    className="flex max-w-lg gap-2"
                    onSubmit={(event) => {
                      event.preventDefault()
                      if (name.trim()) rename.mutate({ id: analysis.id, value: name })
                    }}
                  >
                    <label className="sr-only" htmlFor={`rename-${analysis.id}`}>
                      Analysis name
                    </label>
                    <input
                      id={`rename-${analysis.id}`}
                      className="field py-2"
                      autoFocus
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                    />
                    <button className="btn-primary min-h-10 py-2">Save</button>
                    <button
                      type="button"
                      className="btn-secondary min-h-10 py-2"
                      onClick={() => setRenaming(null)}
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <>
                    <h2 className="truncate font-display text-lg font-bold">{analysis.name}</h2>
                    <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-stone-500 dark:text-stone-400">
                      <span>{analysis.target_job_title || 'Target role'}</span>
                      {analysis.target_employer && <span>· {analysis.target_employer}</span>}
                      <span className="inline-flex items-center gap-1">
                        <Calendar className="size-3" />
                        {new Date(analysis.updated_at).toLocaleDateString()}
                      </span>
                      <span className="rounded-full bg-stone-100 px-2 py-0.5 dark:bg-stone-800">
                        {analysis.state}
                      </span>
                    </p>
                  </>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Link
                  className="rounded-lg p-2 text-stone-500 hover:bg-stone-100 hover:text-moss-700 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-moss-300"
                  to={`/analyses/${analysis.id}`}
                  aria-label={`Open ${analysis.name}`}
                >
                  <ExternalLink className="size-4" />
                </Link>
                <button
                  className="rounded-lg p-2 text-stone-500 hover:bg-stone-100 hover:text-moss-700 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-moss-300"
                  onClick={() => {
                    rename.reset()
                    setRenaming(analysis.id)
                    setName(analysis.name)
                  }}
                  aria-label={`Rename ${analysis.name}`}
                >
                  <Pencil className="size-4" />
                </button>
                <button
                  className="rounded-lg p-2 text-stone-500 hover:bg-red-50 hover:text-red-600 dark:text-stone-400 dark:hover:bg-red-950 dark:hover:text-red-400"
                  onClick={() => setDeleting(analysis.id)}
                  aria-label={`Delete ${analysis.name}`}
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
              {renaming === analysis.id && rename.isError && (
                <p className="text-sm text-red-600 dark:text-red-400" role="alert">
                  {rename.error.message}
                </p>
              )}
              {deleting === analysis.id && (
                <DeleteAnalysisDialog
                  analysisName={analysis.name}
                  pending={remove.isPending}
                  error={remove.error?.message}
                  onCancel={() => setDeleting(null)}
                  onDelete={() => remove.mutate(analysis.id)}
                />
              )}
            </article>
          ))}
        </div>
      )}
    </>
  )
}

function DeleteAnalysisDialog({
  analysisName,
  pending,
  error,
  onCancel,
  onDelete,
}: {
  analysisName: string
  pending: boolean
  error?: string
  onCancel: () => void
  onDelete: () => void
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (typeof dialog.showModal === 'function') dialog.showModal()
    else dialog.setAttribute('open', '')
    return () => {
      if (typeof dialog.close === 'function' && dialog.open) dialog.close()
    }
  }, [])

  return (
    <dialog
      ref={dialogRef}
      className="m-auto w-[calc(100%-2rem)] max-w-md border-0 bg-transparent p-0 text-stone-900 backdrop:bg-stone-950/50 dark:text-stone-100"
      aria-labelledby="delete-title"
      aria-describedby="delete-description"
      onCancel={(event) => {
        event.preventDefault()
        onCancel()
      }}
    >
      <div className="card p-6">
        <h2 id="delete-title" className="font-display text-xl font-bold">
          Delete this analysis?
        </h2>
        <p
          id="delete-description"
          className="mt-3 text-sm leading-6 text-stone-600 dark:text-stone-300"
        >
          This permanently removes “{analysisName}”, its model output, exports, and source
          résumé/job data when they are not shared by another analysis.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="btn-primary bg-red-700 hover:bg-red-800 dark:bg-red-600"
            disabled={pending}
            onClick={onDelete}
          >
            {pending ? 'Deleting…' : 'Delete permanently'}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400" role="alert">
            {error}
          </p>
        )}
      </div>
    </dialog>
  )
}
