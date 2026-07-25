import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { FileText, LockKeyhole, Upload } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'

const schema = z.object({
  resumeText: z.string().trim().min(50, 'Add at least 50 characters of résumé text.'),
})
type FormValues = z.infer<typeof schema>

export function NewAnalysisPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'paste' | 'upload'>('paste')
  const [file, setFile] = useState<File | null>(null)
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { resumeText: '' },
  })
  const createText = useMutation({
    mutationFn: ({ resumeText }: FormValues) => api.createTextResume(resumeText),
    onSuccess: (resume) => navigate(`/resumes/${resume.id}/review`),
  })
  const upload = useMutation({
    mutationFn: (selected: File) => api.uploadResume(selected),
    onSuccess: (resume) => navigate(`/resumes/${resume.id}/review`),
  })
  const pending = createText.isPending || upload.isPending
  const error = createText.error || upload.error

  return (
    <>
      <PageHeader
        eyebrow="Step 1 of 3"
        title="Add your résumé"
        description="Paste text or upload a PDF/DOCX. You will review and correct the extraction before anything is analyzed."
      />
      <div className="mx-auto max-w-4xl">
        {/*
          These were role="tab" without tabpanels, roving tabindex, or arrow-key
          handling, so assistive technology announced a tab list that did not work.
          Toggle buttons describe the actual behaviour.
        */}
        <div
          className="mb-5 grid grid-cols-2 gap-2 rounded-2xl border bg-stone-100 p-1.5 dark:bg-stone-900"
          role="group"
          aria-label="Résumé source"
        >
          <button
            type="button"
            aria-pressed={mode === 'paste'}
            onClick={() => setMode('paste')}
            className={`flex min-h-12 items-center justify-center gap-2 rounded-xl text-sm font-semibold ${mode === 'paste' ? 'bg-white shadow-sm dark:bg-stone-800' : 'text-stone-500 dark:text-stone-400'}`}
          >
            <FileText className="size-4" aria-hidden="true" /> Paste text
          </button>
          <button
            type="button"
            aria-pressed={mode === 'upload'}
            onClick={() => setMode('upload')}
            className={`flex min-h-12 items-center justify-center gap-2 rounded-xl text-sm font-semibold ${mode === 'upload' ? 'bg-white shadow-sm dark:bg-stone-800' : 'text-stone-500 dark:text-stone-400'}`}
          >
            <Upload className="size-4" aria-hidden="true" /> Upload file
          </button>
        </div>

        <div className="card p-5 sm:p-7">
          {mode === 'paste' ? (
            <form
              onSubmit={(event) =>
                void form.handleSubmit((values) => createText.mutate(values))(event)
              }
            >
              <label htmlFor="resume-text" className="text-sm font-semibold">
                Résumé text
              </label>
              <textarea
                id="resume-text"
                className="field mt-2 min-h-[360px] resize-y font-mono text-[13px] leading-6"
                placeholder={'Your Name\nContact details\n\nEXPERIENCE\n...'}
                aria-invalid={form.formState.errors.resumeText ? true : undefined}
                aria-describedby={
                  form.formState.errors.resumeText ? 'resume-text-error' : undefined
                }
                {...form.register('resumeText')}
              />
              {form.formState.errors.resumeText && (
                <p
                  id="resume-text-error"
                  className="mt-2 text-sm text-red-600 dark:text-red-400"
                  role="alert"
                >
                  {form.formState.errors.resumeText.message}
                </p>
              )}
              <div className="mt-5 flex justify-end">
                <button className="btn-primary" disabled={pending}>
                  {pending ? 'Saving…' : 'Review résumé text'}
                </button>
              </div>
            </form>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault()
                if (file) upload.mutate(file)
              }}
            >
              {/*
                The input itself is sr-only, so its focus ring is clipped to 1x1 px.
                The visible drop zone has to carry the indicator instead.
              */}
              <label
                htmlFor="resume-file"
                className="flex min-h-[320px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-stone-400 bg-stone-50 px-6 text-center hover:border-moss-500 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-moss-500 has-[:focus-visible]:ring-offset-2 dark:border-stone-600 dark:bg-stone-950"
              >
                <span className="grid size-14 place-items-center rounded-2xl bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200">
                  <Upload className="size-6" aria-hidden="true" />
                </span>
                <span className="mt-5 font-display text-lg font-bold">
                  {file ? file.name : 'Choose a PDF or DOCX'}
                </span>
                <span className="mt-2 text-sm text-stone-500 dark:text-stone-400">
                  Server-enforced size limit · image-only PDFs require pasted OCR text
                </span>
              </label>
              <input
                id="resume-file"
                className="sr-only"
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              <div className="mt-5 flex justify-end">
                <button className="btn-primary" disabled={!file || pending}>
                  {pending ? 'Extracting…' : 'Extract and review'}
                </button>
              </div>
            </form>
          )}
          {error && (
            <p
              className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200"
              role="alert"
            >
              {error.message}
            </p>
          )}
        </div>
        <p className="mt-4 flex items-center justify-center gap-2 text-xs text-stone-500 dark:text-stone-400">
          <LockKeyhole className="size-3.5" /> Routine logs never include résumé content.
        </p>
      </div>
    </>
  )
}
