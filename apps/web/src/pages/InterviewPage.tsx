import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, BrainCircuit, MessageCircleQuestion, ShieldAlert } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/Status'
import type { InterviewQuestion } from '../types/domain'

export function InterviewPage() {
  const { analysisId = '' } = useParams()
  const analysis = useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => api.getAnalysis(analysisId),
  })
  if (analysis.isLoading) return <LoadingState label="Loading interview preparation" />
  if (analysis.isError) return <ErrorState message={analysis.error.message} />
  if (!analysis.data) return null
  const groups: Array<{
    key: InterviewQuestion['category']
    title: string
    description: string
    icon: typeof BrainCircuit
  }> = [
    {
      key: 'technical',
      title: 'Technical & role-specific',
      description: 'Questions based on explicit skill overlap.',
      icon: BrainCircuit,
    },
    {
      key: 'behavioral',
      title: 'Behavioral',
      description: 'Prompts grounded in responsibilities already shown.',
      icon: MessageCircleQuestion,
    },
    {
      key: 'experience_gap',
      title: 'Experience gaps',
      description: 'Honest ways to prepare for unsupported requirements.',
      icon: ShieldAlert,
    },
  ]
  return (
    <>
      <PageHeader
        eyebrow="Evidence-led preparation"
        title="Interview focus areas"
        description="These prompts organize the résumé and job-description evidence you supplied. They are not scripts; résumé talking points quote stored evidence and still require review."
        actions={
          <Link className="btn-secondary" to={`/analyses/${analysisId}`}>
            <ArrowLeft className="size-4" /> Results
          </Link>
        }
      />
      <div className="space-y-7">
        {groups.map(({ key, title, description, icon: Icon }) => {
          const questions = analysis.data.interview_questions.filter(
            (item) => item.category === key,
          )
          return (
            <section key={key}>
              <div className="mb-3 flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-xl bg-moss-100 text-moss-800 dark:bg-moss-900 dark:text-moss-200">
                  <Icon className="size-4" />
                </span>
                <div>
                  <h2 className="font-display text-lg font-bold">{title}</h2>
                  <p className="text-xs text-stone-500 dark:text-stone-400">{description}</p>
                </div>
              </div>
              {questions.length ? (
                <div className="grid gap-4 lg:grid-cols-2">
                  {questions.map((question) => (
                    <article className="card p-5" key={question.id}>
                      <div className="flex flex-wrap gap-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                          {question.confidence} confidence
                        </span>
                        {question.source === 'model' && (
                          <span className="text-[10px] font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">
                            model-generated
                          </span>
                        )}
                      </div>
                      <h3 className="mt-2 font-display text-lg font-bold leading-7">
                        {question.question}
                      </h3>
                      {question.resume_evidence ? (
                        <blockquote className="mt-4 border-l-2 border-moss-400 pl-3 text-sm italic leading-6 text-stone-600 dark:text-stone-300">
                          “{question.resume_evidence}”
                        </blockquote>
                      ) : (
                        <p className="mt-4 text-sm text-amber-700 dark:text-amber-300">
                          No résumé evidence was found for this requirement.
                        </p>
                      )}
                      {question.talking_points.length > 0 && (
                        <div className="mt-4 rounded-xl bg-stone-50 p-3 dark:bg-stone-950">
                          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-stone-400">
                            Talking points from your résumé
                          </p>
                          <ul className="mt-2 space-y-1.5 text-sm leading-6">
                            {question.talking_points.map((point) => (
                              <li key={point}>• {point}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              ) : (
                <div className="card border-dashed p-5 text-sm text-stone-500 dark:text-stone-400">
                  No questions in this category.
                </div>
              )}
            </section>
          )
        })}
      </div>
    </>
  )
}
