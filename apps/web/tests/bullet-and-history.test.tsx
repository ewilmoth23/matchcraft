import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { analysisFixture, jsonResponse, mockFetch, renderApp, resumeFixture } from './helpers'

describe('bullet workshop and history', () => {
  it('marks rewrite placeholders and confirmation requirements', async () => {
    const user = userEvent.setup()
    mockFetch((url) => {
      if (url.endsWith('/analyses/analysis-1/bullet-rewrite')) {
        return jsonResponse({
          original_bullet: 'Built Python services.',
          suggested_bullet: 'Built Python services — resulting in [insert verified outcome].',
          reason: 'Adds a clearly marked outcome placeholder.',
          factual_sources: ['Built Python services.'],
          confirmation_required: true,
          model_generated: false,
          warning: 'Review every word and verify placeholders.',
        })
      }
      if (url.endsWith('/analyses/analysis-1')) return jsonResponse(analysisFixture)
      if (url.endsWith('/resumes/resume-1')) return jsonResponse(resumeFixture)
      return jsonResponse({}, 404)
    })
    renderApp('/analyses/analysis-1/bullets')
    expect(await screen.findByText('Role overlap')).toBeInTheDocument()
    expect(screen.getByText('25%')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: /generate safe rewrite/i }))
    expect(await screen.findByText(/insert verified outcome/i)).toBeInTheDocument()
    expect(screen.getAllByText(/confirmation required/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Review every word and verify placeholders/i)).toBeInTheDocument()
  })

  it('requires explicit deletion confirmation', async () => {
    const user = userEvent.setup()
    let deleted = false
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/analyses/analysis-1') && init?.method === 'DELETE') {
        deleted = true
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      if (url.endsWith('/analyses')) {
        return jsonResponse(deleted ? [] : [analysisFixture])
      }
      return jsonResponse({}, 404)
    })
    renderApp('/history')
    await user.click(
      await screen.findByRole('button', { name: /Delete Senior Software Engineer/i }),
    )
    expect(screen.getByRole('dialog')).toHaveTextContent('Delete this analysis?')
    await user.click(screen.getByRole('button', { name: /Delete permanently/i }))
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/analyses/analysis-1'),
        expect.objectContaining({ method: 'DELETE' }),
      ),
    )
  })

  it('updates the cached analysis detail after a rename', async () => {
    const user = userEvent.setup()
    const renamedAnalysis = { ...analysisFixture, name: 'Release acceptance analysis' }
    mockFetch((url, init) => {
      if (url.endsWith('/analyses/analysis-1') && init?.method === 'PATCH') {
        return jsonResponse(renamedAnalysis)
      }
      if (url.endsWith('/analyses')) return jsonResponse([analysisFixture])
      return jsonResponse({}, 404)
    })
    const { queryClient } = renderApp('/history')
    queryClient.setQueryData(['analysis', 'analysis-1'], analysisFixture)

    await user.click(
      await screen.findByRole('button', { name: /Rename Senior Software Engineer/i }),
    )
    await user.clear(screen.getByLabelText('Analysis name'))
    await user.type(screen.getByLabelText('Analysis name'), renamedAnalysis.name)
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(queryClient.getQueryData(['analysis', 'analysis-1'])).toEqual(renamedAnalysis),
    )
  })
})
