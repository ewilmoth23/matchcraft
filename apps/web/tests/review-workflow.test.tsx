import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { jobFixture, jsonResponse, mockFetch, renderApp, resumeFixture } from './helpers'

describe('review workflow', () => {
  it('saves corrected résumé text and requires confirmation before the job step', async () => {
    const user = userEvent.setup()
    const corrected = {
      ...resumeFixture,
      extracted_text: `${resumeFixture.extracted_text}\nEDUCATION`,
    }
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/resumes/resume-1/confirm'))
        return jsonResponse({ ...corrected, confirmed: true })
      if (url.endsWith('/resumes/resume-1') && init?.method === 'PUT')
        return jsonResponse(corrected)
      if (url.endsWith('/resumes/resume-1')) return jsonResponse(resumeFixture)
      return jsonResponse({}, 404)
    })
    const { queryClient } = renderApp('/resumes/resume-1/review')
    const textarea = await screen.findByLabelText(/extracted résumé text/i)
    await user.type(textarea, '\nEDUCATION')
    await user.click(screen.getByRole('button', { name: /confirm and continue/i }))
    expect(
      await screen.findByRole('heading', { name: /review the target role/i }),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/resumes/resume-1'),
      expect.objectContaining({ method: 'PUT' }),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/resumes/resume-1/confirm'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(queryClient.getQueryData(['resume', 'resume-1'])).toEqual({
      ...corrected,
      confirmed: true,
    })
  })

  it('shows required and preferred classifications before analysis', async () => {
    const user = userEvent.setup()
    mockFetch((url) => {
      if (url.endsWith('/job-descriptions')) return jsonResponse(jobFixture, 201)
      return jsonResponse({}, 404)
    })
    renderApp('/jobs/review?resume=resume-1')
    await user.type(screen.getByLabelText(/job description/i), jobFixture.raw_text)
    await user.click(screen.getByRole('button', { name: /parse requirements/i }))
    expect(await screen.findByText('Python')).toBeInTheDocument()
    expect(screen.getByText('Kubernetes')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Required' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Preferred' })).toBeInTheDocument()
  })

  it('requires edited job text to be reparsed and reviewed again', async () => {
    const user = userEvent.setup()
    const updatedText = `${jobFixture.raw_text}\nAn additional qualification was added.`
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/job-descriptions/job-1') && init?.method === 'PUT')
        return jsonResponse({ ...jobFixture, raw_text: updatedText })
      if (url.endsWith('/job-descriptions')) return jsonResponse(jobFixture, 201)
      return jsonResponse({}, 404)
    })
    renderApp('/jobs/review?resume=resume-1')
    const textarea = screen.getByLabelText(/job description/i)
    await user.type(textarea, jobFixture.raw_text)
    await user.click(screen.getByRole('button', { name: /parse requirements/i }))
    expect(await screen.findByRole('button', { name: /run analysis/i })).toBeInTheDocument()

    await user.type(textarea, '\nAn additional qualification was added.')

    expect(screen.getByRole('heading', { name: /text changed/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /run analysis/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /parse requirements/i })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)
    await user.click(screen.getByRole('button', { name: /parse requirements/i }))
    expect(await screen.findByRole('button', { name: /run analysis/i })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/job-descriptions/job-1'),
      expect.objectContaining({ method: 'PUT' }),
    )
  })
})
