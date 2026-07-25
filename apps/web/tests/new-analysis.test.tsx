import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { jsonResponse, mockFetch, renderApp, resumeFixture } from './helpers'

describe('new analysis', () => {
  it('uploads a DOCX and advances to extraction review', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/resumes/upload')) return jsonResponse(resumeFixture, 201)
      if (url.endsWith('/resumes/resume-1')) return jsonResponse(resumeFixture)
      return jsonResponse({}, 404)
    })
    renderApp('/analyses/new')
    const uploadToggle = await screen.findByRole('button', { name: /upload file/i })
    expect(uploadToggle).toHaveAttribute('aria-pressed', 'false')
    await user.click(uploadToggle)
    expect(screen.getByRole('button', { name: /upload file/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    const file = new File(['document'], 'resume.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    await user.upload(screen.getByLabelText(/choose a pdf or docx/i), file)
    await user.click(screen.getByRole('button', { name: /extract and review/i }))
    expect(
      await screen.findByRole('heading', { name: /review the extraction/i }),
    ).toBeInTheDocument()
    const uploadCall = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
      return url.includes('/resumes/upload')
    })
    expect(uploadCall?.[1]?.method).toBe('POST')
    expect(uploadCall?.[1]?.body).toBeInstanceOf(FormData)
  })

  it('shows API errors instead of losing the form', async () => {
    const user = userEvent.setup()
    mockFetch(() =>
      jsonResponse(
        { error: { code: 'database_error', message: 'Local database is unavailable.' } },
        503,
      ),
    )
    renderApp('/analyses/new')
    await user.type(
      await screen.findByLabelText(/résumé text/i),
      'Jordan Rivera experience building reliable Python services and testing data systems.',
    )
    await user.click(screen.getByRole('button', { name: /review résumé text/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Local database is unavailable.')
    await waitFor(() =>
      expect(screen.getByLabelText<HTMLTextAreaElement>(/résumé text/i).value).toContain(
        'Jordan Rivera',
      ),
    )
  })
})
