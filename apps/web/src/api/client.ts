import type {
  Analysis,
  AnalysisSummary,
  AppSettings,
  BulletRewrite,
  Health,
  JobDescription,
  Recommendation,
  Resume,
} from '../types/domain'

const environment = import.meta.env as unknown as { readonly VITE_API_URL?: string }
const API_URL = environment.VITE_API_URL || 'http://localhost:8000/api/v1'

type ErrorEnvelope = {
  error?: { code?: string; message?: string; details?: unknown }
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code = 'request_failed',
  ) {
    super(message)
  }
}

// HTTP/2 responses carry no statusText, so a status-only failure must still read as
// something a person can act on rather than an empty string.
const STATUS_MESSAGES: Record<number, string> = {
  404: 'That item no longer exists. It may have been deleted.',
  409: 'This step is not available yet. Review and confirm the earlier step first.',
  413: 'That file is larger than the configured upload limit.',
  415: 'That file type is not supported. Upload a PDF or DOCX résumé.',
  422: 'The request could not be validated. Check the supplied text or file.',
  500: 'The local API could not complete the request. Check its logs.',
  502: 'The local API is not responding correctly. Check that it is running.',
  503: 'The local API is unavailable. Check that it is running.',
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...init?.headers,
      },
    })
  } catch {
    // fetch rejects on transport failure, which otherwise surfaced the browser's
    // internal "Failed to fetch" string directly in the UI.
    throw new ApiError(
      'Could not reach the MatchCraft API. Check that the local server is running.',
      0,
      'network_error',
    )
  }
  if (!response.ok) {
    let envelope: ErrorEnvelope = {}
    try {
      envelope = (await response.json()) as ErrorEnvelope
    } catch {
      // The status message remains a safe fallback for non-JSON proxy errors.
    }
    throw new ApiError(
      envelope.error?.message ||
        STATUS_MESSAGES[response.status] ||
        response.statusText ||
        `Request failed (HTTP ${response.status}).`,
      response.status,
      envelope.error?.code,
    )
  }
  if (response.status === 204) return undefined as T
  try {
    return (await response.json()) as T
  } catch {
    // A 2xx that is not JSON means a proxy answered instead of the API.
    throw new ApiError(
      'The API returned an unexpected response. Check that VITE_API_URL points at the MatchCraft API.',
      response.status,
      'invalid_response',
    )
  }
}

export const api = {
  health: () => request<Health>('/health'),
  createTextResume: (text: string) =>
    request<Resume>('/resumes/text', { method: 'POST', body: JSON.stringify({ text }) }),
  uploadResume: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<Resume>('/resumes/upload', { method: 'POST', body })
  },
  getResume: (id: string) => request<Resume>(`/resumes/${id}`),
  updateResume: (id: string, extractedText: string) =>
    request<Resume>(`/resumes/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ extracted_text: extractedText }),
    }),
  confirmResume: (id: string) => request<Resume>(`/resumes/${id}/confirm`, { method: 'POST' }),
  createJob: (text: string) =>
    request<JobDescription>('/job-descriptions', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  updateJob: (id: string, text: string) =>
    request<JobDescription>(`/job-descriptions/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ text }),
    }),
  createAnalysis: (resumeId: string, jobDescriptionId: string) =>
    request<Analysis>('/analyses', {
      method: 'POST',
      body: JSON.stringify({ resume_id: resumeId, job_description_id: jobDescriptionId }),
    }),
  runAnalysis: (id: string, useModel: boolean) =>
    request<Analysis>(`/analyses/${id}/run`, {
      method: 'POST',
      body: JSON.stringify({ use_model: useModel }),
    }),
  getAnalysis: (id: string) => request<Analysis>(`/analyses/${id}`),
  listAnalyses: () => request<AnalysisSummary[]>('/analyses'),
  renameAnalysis: (id: string, name: string) =>
    request<Analysis>(`/analyses/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  deleteAnalysis: (id: string) => request<void>(`/analyses/${id}`, { method: 'DELETE' }),
  updateRecommendation: (analysisId: string, recommendationId: string, status: string) =>
    request<Recommendation>(`/analyses/${analysisId}/recommendations/${recommendationId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  rewriteBullet: (analysisId: string, originalBullet: string) =>
    request<BulletRewrite>(`/analyses/${analysisId}/bullet-rewrite`, {
      method: 'POST',
      body: JSON.stringify({ original_bullet: originalBullet }),
    }),
  getSettings: () => request<AppSettings>('/settings'),
  updateSettings: (values: Partial<AppSettings>) =>
    request<AppSettings>('/settings', { method: 'PUT', body: JSON.stringify(values) }),
  exportUrl: (id: string, format: 'markdown' | 'json') =>
    `${API_URL}/analyses/${id}/export/${format}`,
  // Browsers ignore the download attribute on a cross-origin href, so a direct link
  // navigated away from the app whenever the API was on a different port.
  downloadExport: async (id: string, format: 'markdown' | 'json') => {
    let response: Response
    try {
      response = await fetch(api.exportUrl(id, format))
    } catch {
      throw new ApiError(
        'Could not reach the MatchCraft API. Check that the local server is running.',
        0,
        'network_error',
      )
    }
    if (!response.ok) {
      throw new ApiError(
        STATUS_MESSAGES[response.status] || 'The export could not be downloaded.',
        response.status,
        'export_failed',
      )
    }
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    try {
      link.href = objectUrl
      link.download = `matchcraft-${id}.${format === 'markdown' ? 'md' : 'json'}`
      document.body.appendChild(link)
      link.click()
    } finally {
      link.remove()
      // Deferred so the browser has started reading the blob before it is released.
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    }
  },
}
