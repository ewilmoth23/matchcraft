import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '../src/api/client'
import { analysisFixture, jsonResponse, mockFetch, renderApp } from './helpers'

describe('api client error handling', () => {
  it('reports a reachable message when the API is down instead of "Failed to fetch"', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    await expect(api.health()).rejects.toMatchObject({
      code: 'network_error',
      status: 0,
    })
    await expect(api.health()).rejects.toThrow(/Could not reach the MatchCraft API/)
  })

  it('maps a status-only failure to an actionable message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response('', { status: 503, statusText: '' }))),
    )
    await expect(api.health()).rejects.toThrow(/local API is unavailable/i)
  })

  it('does not surface a raw SyntaxError when a proxy answers a 2xx with HTML', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response('<!doctype html><html></html>', {
            status: 200,
            headers: { 'Content-Type': 'text/html' },
          }),
        ),
      ),
    )
    await expect(api.health()).rejects.toBeInstanceOf(ApiError)
    await expect(api.health()).rejects.toThrow(/unexpected response/i)
  })
})

describe('results accessibility and cache behaviour', () => {
  it('hides the decorative chart from assistive technology and keeps the text equivalent', async () => {
    mockFetch((url) => {
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(analysisFixture)
      return jsonResponse({}, 404)
    })
    const { container } = renderApp('/analyses/analysis-1')
    await screen.findByLabelText('72 out of 100')
    const chart = container.querySelector('[aria-hidden="true"] .recharts-responsive-container')
    expect(chart).not.toBeNull()
    // Every charted value is still available as text.
    expect(screen.getByText('Required skill alignment')).toBeInTheDocument()
    expect(screen.getByText('20 / 25')).toBeInTheDocument()
  })

  it('invalidates the saved-analyses list after a rerun so history is not stale', async () => {
    const user = userEvent.setup()
    mockFetch((url) => {
      if (url.endsWith('/analyses/analysis-1/run'))
        return jsonResponse({ ...analysisFixture, overall_score: 91 })
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(analysisFixture)
      return jsonResponse([], 200)
    })
    const { queryClient } = renderApp('/analyses/analysis-1')
    queryClient.setQueryData(['analyses'], [{ id: 'analysis-1', overall_score: 72 }])
    await screen.findByLabelText('72 out of 100')
    await user.click(screen.getByRole('button', { name: /rerun/i }))
    await waitFor(() => {
      expect(queryClient.getQueryState(['analyses'])?.isInvalidated).toBe(true)
    })
  })
})

describe('results export failures', () => {
  it('shows an error instead of failing silently when an export cannot be downloaded', async () => {
    const user = userEvent.setup()
    mockFetch((url) => {
      if (url.includes('/export/')) return jsonResponse({}, 500)
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(analysisFixture)
      return jsonResponse({}, 404)
    })
    renderApp('/analyses/analysis-1')
    await screen.findByLabelText('72 out of 100')
    await user.click(screen.getByRole('button', { name: /Markdown/i }))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/local API could not complete|export/i)
    })
  })
})

describe('history accessibility', () => {
  it('announces a deletion and returns focus to the page heading', async () => {
    const user = userEvent.setup()
    let deleted = false
    mockFetch((url, init) => {
      if (init?.method === 'DELETE') {
        deleted = true
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      if (url.endsWith('/analyses'))
        return jsonResponse(
          deleted
            ? []
            : [
                {
                  id: 'analysis-1',
                  name: 'Senior Software Engineer — Acme',
                  state: 'completed',
                  overall_score: 72,
                  model_status: 'unavailable',
                  created_at: '2026-07-18T00:00:00Z',
                  updated_at: '2026-07-18T00:00:00Z',
                  target_job_title: 'Senior Software Engineer',
                  target_employer: 'Acme',
                },
              ],
        )
      return jsonResponse({}, 404)
    })
    renderApp('/history')
    await user.click(await screen.findByRole('button', { name: /delete/i }))
    await user.click(await screen.findByRole('button', { name: /delete permanently/i }))
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/Deleted Senior Software Engineer/i)
    })
    // Focus is deferred one frame so the closing <dialog> cannot override it.
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1 }))
    })
  })
})
