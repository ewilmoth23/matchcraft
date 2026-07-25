import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { analysisFixture, jsonResponse, mockFetch, renderApp } from './helpers'

describe('results', () => {
  it('displays scores, matched evidence, gaps, recommendations, exports, and provider state', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch((url) => {
      if (url.includes('/export/')) return jsonResponse({})
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(analysisFixture)
      return jsonResponse({}, 404)
    })
    renderApp('/analyses/analysis-1')
    expect(await screen.findByLabelText('72 out of 100')).toBeInTheDocument()
    expect(screen.getByText('Matched (1)')).toBeInTheDocument()
    expect(screen.getByText('Unsupported (1)')).toBeInTheDocument()
    expect(screen.getAllByText('Python').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Kubernetes').length).toBeGreaterThan(0)
    expect(screen.getByText('Verify evidence for Kubernetes')).toBeInTheDocument()
    expect(screen.getByText('20 / 25')).toBeInTheDocument()
    expect(screen.getByText('Python has contextual evidence.')).toBeInTheDocument()
    expect(screen.getByText(/AI unavailable/i)).toBeInTheDocument()
    // Exports fetch a blob rather than following a cross-origin href, which browsers
    // treat as a navigation and which loses the application state.
    await user.click(screen.getByRole('button', { name: /Markdown/i }))
    const exportCall = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
      return url.includes('/export/markdown')
    })
    expect(exportCall).toBeDefined()
  })

  it('shows progress while deterministic analysis is running', async () => {
    const ready = {
      ...analysisFixture,
      state: 'ready' as const,
      deterministic_complete: false,
      scores: [],
      evidence: [],
      recommendations: [],
      interview_questions: [],
    }
    let finishRun: ((response: Response) => void) | undefined
    mockFetch((url) => {
      if (url.endsWith('/analyses/analysis-1/run')) {
        return new Promise<Response>((resolve) => {
          finishRun = resolve
        })
      }
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(ready)
      return jsonResponse({}, 404)
    })
    renderApp('/analyses/analysis-1?run=1&ai=0')
    expect(await screen.findByText('Analysis in progress')).toBeInTheDocument()
    finishRun?.(new Response(JSON.stringify(analysisFixture), { status: 200 }))
    expect(await screen.findByLabelText('72 out of 100')).toBeInTheDocument()
  })

  it('labels and explains validated model-assisted findings', async () => {
    const modelFixture = {
      ...analysisFixture,
      model_status: 'completed',
      result: {
        ...analysisFixture.result,
        model_generated: true,
        model_executive_summary: 'The supplied evidence supports part of the target role.',
        model_responsibility_alignment: 0.5,
        model_transferable_experience: ['Built Python services.'],
      },
    }
    mockFetch((url) => {
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(modelFixture)
      return jsonResponse({}, 404)
    })

    renderApp('/analyses/analysis-1')

    expect(await screen.findByText('Model-generated summary')).toBeInTheDocument()
    expect(screen.getByText(/responsibility overlap: 50%/i)).toBeInTheDocument()
    expect(screen.getAllByText('“Built Python services.”').length).toBeGreaterThan(0)
  })

  it('shows a retryable error when analysis fails before deterministic results exist', async () => {
    const ready = {
      ...analysisFixture,
      state: 'ready' as const,
      deterministic_complete: false,
      scores: [],
      evidence: [],
      recommendations: [],
      interview_questions: [],
    }
    mockFetch((url) => {
      if (url.endsWith('/analyses/analysis-1/run'))
        return jsonResponse(
          { error: { code: 'analysis_failed', message: 'The analysis could not be completed.' } },
          500,
        )
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(ready)
      return jsonResponse({}, 404)
    })

    renderApp('/analyses/analysis-1?run=1&ai=0')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The analysis could not be completed.',
    )
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
    expect(screen.queryByText(/preparing analysis/i)).not.toBeInTheDocument()
  })

  it('makes a saved but unrun analysis actionable when reopened from history', async () => {
    const ready = {
      ...analysisFixture,
      state: 'ready' as const,
      deterministic_complete: false,
      scores: [],
      evidence: [],
      recommendations: [],
      interview_questions: [],
    }
    mockFetch((url) => {
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(ready)
      if (url.endsWith('/analyses/analysis-1/run')) return jsonResponse(analysisFixture)
      return jsonResponse({}, 404)
    })

    renderApp('/analyses/analysis-1')

    expect(await screen.findByRole('alert')).toHaveTextContent('has not been run yet')
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
