import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import { App } from '../src/routes/App'
import type { Analysis, JobDescription, Resume } from '../src/types/domain'

export function renderApp(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { ...rendered, queryClient }
}

export function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

export function mockFetch(handler: (url: string, init?: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    return handler(url, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export const resumeFixture: Resume = {
  id: 'resume-1',
  source_type: 'text',
  original_filename: null,
  media_type: null,
  file_size: null,
  original_text: 'Jordan Rivera\nEXPERIENCE\n• Built Python services.',
  extracted_text: 'Jordan Rivera\nEXPERIENCE\n• Built Python services.',
  structured_data: {
    name: 'Jordan Rivera',
    skills: ['Python'],
    bullets: ['Built Python services.'],
    sections: [{ kind: 'experience', heading: 'EXPERIENCE', content: '• Built Python services.' }],
  },
  extraction_warnings: [],
  confirmed: true,
  created_at: '2026-07-18T00:00:00Z',
  updated_at: '2026-07-18T00:00:00Z',
}

export const jobFixture: JobDescription = {
  id: 'job-1',
  raw_text:
    'Senior Software Engineer\nRequired Qualifications\nPython is required.\nPreferred Qualifications\nKubernetes preferred.',
  title: 'Senior Software Engineer',
  employer: 'Acme Public Systems',
  location: 'Remote',
  structured_data: {},
  requirements: [
    {
      id: 'req-1',
      category: 'skill',
      text: 'Python',
      normalized_key: 'python',
      priority: 'required',
      explicitness: 'explicit',
      source_excerpt: 'Python is required.',
    },
    {
      id: 'req-2',
      category: 'skill',
      text: 'Kubernetes',
      normalized_key: 'kubernetes',
      priority: 'preferred',
      explicitness: 'explicit',
      source_excerpt: 'Kubernetes preferred.',
    },
  ],
  created_at: '2026-07-18T00:00:00Z',
  updated_at: '2026-07-18T00:00:00Z',
}

export const analysisFixture: Analysis = {
  id: 'analysis-1',
  name: 'Senior Software Engineer — Acme Public Systems',
  state: 'completed',
  overall_score: 72,
  model_status: 'unavailable',
  created_at: '2026-07-18T00:00:00Z',
  updated_at: '2026-07-18T00:00:00Z',
  target_job_title: 'Senior Software Engineer',
  target_employer: 'Acme Public Systems',
  resume_id: 'resume-1',
  job_description_id: 'job-1',
  deterministic_complete: true,
  result: {
    top_strengths: ['Python'],
    top_gaps: ['Kubernetes'],
    transferable_experience: [],
    bullet_analysis: [
      {
        original_bullet: 'Built Python services.',
        action_verb: 'built',
        action_led: true,
        task_clarity: 'medium',
        technical_detail: ['Python'],
        business_impact: false,
        measurable_outcome: false,
        job_relevance: 0.25,
        length_words: 3,
        redundant_phrases: [],
        unsupported_claims: [],
        verification_note: 'User-supplied résumé claims are not independently verified.',
      },
    ],
    disclaimer: 'This does not predict hiring outcomes.',
  },
  error_message: null,
  scores: [
    {
      id: 'score-1',
      category: 'Required skill alignment',
      score: 20,
      maximum: 25,
      reason: 'Python has contextual evidence.',
      improvements: [],
    },
    {
      id: 'score-2',
      category: 'Preferred skill alignment',
      score: 0,
      maximum: 10,
      reason: 'Kubernetes was not found.',
      improvements: ['Confirm genuine experience before adding Kubernetes.'],
    },
  ],
  evidence: [
    {
      id: 'evidence-1',
      requirement_id: 'req-1',
      requirement: 'Python',
      status: 'supported',
      resume_excerpt: 'Built Python services.',
      source_section: 'Experience',
      confidence: 'high',
      interpretation: 'Direct terminology match.',
    },
    {
      id: 'evidence-2',
      requirement_id: 'req-2',
      requirement: 'Kubernetes',
      status: 'not_found',
      resume_excerpt: null,
      source_section: null,
      confidence: 'high',
      interpretation: 'No match; this does not prove the candidate lacks the skill.',
    },
  ],
  recommendations: [
    {
      id: 'recommendation-1',
      priority: 'Moderate impact',
      title: 'Verify evidence for Kubernetes',
      explanation: 'No traceable evidence was found.',
      supporting_evidence: null,
      role_reason: 'The job lists it as preferred.',
      recommended_action: 'Add it only if you genuinely have this experience.',
      confidence: 'high',
      confirmation_required: true,
      source: 'deterministic',
      status: 'open',
    },
  ],
  interview_questions: [
    {
      id: 'question-1',
      category: 'technical',
      question: 'How have you applied Python?',
      talking_points: ['Built Python services.'],
      resume_evidence: 'Built Python services.',
      confidence: 'high',
      source: 'deterministic',
    },
  ],
}
