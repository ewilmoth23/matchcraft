import { expect, type Locator, test } from '@playwright/test'

function rgbChannels(value: string) {
  const channels = value
    .match(/[\d.]+/g)
    ?.slice(0, 3)
    .map(Number)
  if (!channels || channels.length !== 3) throw new Error(`Unsupported CSS color: ${value}`)
  return channels
}

function relativeLuminance(value: string) {
  const channels = rgbChannels(value).map((channel) => {
    const normalized = channel / 255
    return normalized <= 0.04045 ? normalized / 12.92 : Math.pow((normalized + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}

function contrastRatio(foreground: string, background: string) {
  const lighter = Math.max(relativeLuminance(foreground), relativeLuminance(background))
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background))
  return (lighter + 0.05) / (darker + 0.05)
}

async function expectReadableText(locator: Locator) {
  await expect
    .poll(
      async () => {
        const colors = await locator.evaluate((element) => {
          const foreground = getComputedStyle(element).color
          let background = 'rgba(0, 0, 0, 0)'
          let current: Element | null = element
          while (current && (background === 'rgba(0, 0, 0, 0)' || background === 'transparent')) {
            background = getComputedStyle(current).backgroundColor
            current = current.parentElement
          }
          return { foreground, background }
        })
        if (colors.background === 'rgba(0, 0, 0, 0)') return 0
        return contrastRatio(colors.foreground, colors.background)
      },
      { message: 'Expected visible text to meet WCAG AA contrast after theme transitions settle' },
    )
    .toBeGreaterThanOrEqual(4.5)
}

async function expectReadablePlaceholder(locator: Locator) {
  await expect
    .poll(
      async () => {
        const colors = await locator.evaluate((element) => ({
          foreground: getComputedStyle(element, '::placeholder').color,
          background: getComputedStyle(element).backgroundColor,
        }))
        return contrastRatio(colors.foreground, colors.background)
      },
      { message: 'Expected placeholder text to meet WCAG AA contrast' },
    )
    .toBeGreaterThanOrEqual(4.5)
}

test('complete local-first analysis workflow', async ({ page }) => {
  const resumeText = `Jordan Rivera
jordan.rivera@example.test

EXPERIENCE
• Built Python services that processed 2 million records each week.
• Reduced validation failures by 32% with automated tests.

SKILLS
Python, FastAPI, SQL, React, TypeScript, Docker

EDUCATION
Bachelor of Science in Information Systems`
  const jobText = `Senior Software Engineer
Company: Acme Public Systems

Required Qualifications
• Python and SQL are required.
• Experience with FastAPI and React is required.

Preferred Qualifications
• Kubernetes preferred.

Responsibilities
• Build reliable services and improve automated testing.`
  const now = '2026-07-18T00:00:00Z'
  const resume = {
    id: 'resume-e2e',
    source_type: 'text',
    original_filename: null,
    media_type: null,
    file_size: null,
    original_text: resumeText,
    extracted_text: resumeText,
    structured_data: {
      name: 'Jordan Rivera',
      skills: ['Python', 'FastAPI', 'SQL', 'React', 'TypeScript', 'Docker'],
      bullets: [
        'Built Python services that processed 2 million records each week.',
        'Reduced validation failures by 32% with automated tests.',
      ],
      sections: [],
    },
    extraction_warnings: [],
    confirmed: false,
    created_at: now,
    updated_at: now,
  }
  const job = {
    id: 'job-e2e',
    raw_text: jobText,
    title: 'Senior Software Engineer',
    employer: 'Acme Public Systems',
    location: null,
    structured_data: {},
    requirements: [
      {
        id: 'req-python',
        category: 'skill',
        text: 'Python',
        normalized_key: 'python',
        priority: 'required',
        explicitness: 'explicit',
        source_excerpt: 'Python and SQL are required.',
      },
      {
        id: 'req-kubernetes',
        category: 'skill',
        text: 'Kubernetes',
        normalized_key: 'kubernetes',
        priority: 'preferred',
        explicitness: 'explicit',
        source_excerpt: 'Kubernetes preferred.',
      },
    ],
    created_at: now,
    updated_at: now,
  }
  const ready = {
    id: 'analysis-e2e',
    name: 'Senior Software Engineer — Acme Public Systems',
    state: 'ready',
    overall_score: null,
    model_status: 'not_requested',
    created_at: now,
    updated_at: now,
    target_job_title: job.title,
    target_employer: job.employer,
    resume_id: resume.id,
    job_description_id: job.id,
    deterministic_complete: false,
    result: {},
    error_message: null,
    scores: [],
    evidence: [],
    recommendations: [],
    interview_questions: [],
  }
  const completed = {
    ...ready,
    state: 'completed',
    overall_score: 78,
    model_status: 'unavailable',
    deterministic_complete: true,
    result: {
      top_strengths: ['Python'],
      top_gaps: ['Kubernetes'],
      transferable_experience: [],
      disclaimer: 'This does not predict hiring outcomes.',
    },
    scores: [
      {
        id: 'score-1',
        category: 'Required skill alignment',
        score: 22,
        maximum: 25,
        reason: 'Python has concrete evidence.',
        improvements: [],
      },
      {
        id: 'score-2',
        category: 'Preferred skill alignment',
        score: 0,
        maximum: 10,
        reason: 'Kubernetes was not found.',
        improvements: [],
      },
    ],
    evidence: [
      {
        id: 'ev-1',
        requirement_id: 'req-python',
        requirement: 'Python',
        status: 'supported',
        resume_excerpt: 'Built Python services that processed 2 million records each week.',
        source_section: 'Experience',
        confidence: 'high',
        interpretation: 'Direct terminology match.',
      },
      {
        id: 'ev-2',
        requirement_id: 'req-kubernetes',
        requirement: 'Kubernetes',
        status: 'not_found',
        resume_excerpt: null,
        source_section: null,
        confidence: 'high',
        interpretation: 'No evidence found; this does not prove the skill is absent.',
      },
    ],
    recommendations: [
      {
        id: 'rec-1',
        priority: 'Moderate impact',
        title: 'Verify evidence for Kubernetes',
        explanation: 'No traceable evidence was found.',
        supporting_evidence: null,
        role_reason: 'The role lists it as preferred.',
        recommended_action: 'Add it only if you genuinely have this experience.',
        confidence: 'high',
        confirmation_required: true,
        source: 'deterministic',
        status: 'open',
      },
    ],
    interview_questions: [],
  }
  let deleted = false

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const method = route.request().method()
    if (path.endsWith('/resumes/text') && method === 'POST') {
      await route.fulfill({ status: 201, json: resume })
    } else if (path.endsWith(`/resumes/${resume.id}`) && method === 'GET') {
      await route.fulfill({ json: resume })
    } else if (path.endsWith(`/resumes/${resume.id}/confirm`)) {
      resume.confirmed = true
      await route.fulfill({ json: resume })
    } else if (path.endsWith('/job-descriptions') && method === 'POST') {
      await route.fulfill({ status: 201, json: job })
    } else if (path.endsWith('/analyses') && method === 'POST') {
      await route.fulfill({ status: 201, json: ready })
    } else if (path.endsWith(`/analyses/${ready.id}/run`)) {
      await route.fulfill({ json: completed })
    } else if (path.endsWith(`/analyses/${ready.id}`) && method === 'GET') {
      await route.fulfill({ json: completed })
    } else if (path.endsWith(`/analyses/${ready.id}/bullet-rewrite`)) {
      await route.fulfill({
        json: {
          original_bullet: resume.structured_data.bullets[0],
          suggested_bullet:
            'Built Python services that processed 2 million records each week — resulting in [insert verified outcome].',
          reason: 'Keeps source facts and marks the unknown outcome.',
          factual_sources: [resume.structured_data.bullets[0]],
          confirmation_required: true,
          model_generated: false,
          warning: 'Review every word before use.',
        },
      })
    } else if (path.endsWith(`/analyses/${ready.id}/export/markdown`)) {
      await route.fulfill({
        status: 200,
        contentType: 'text/markdown',
        headers: { 'Content-Disposition': 'attachment; filename="matchcraft-report.md"' },
        body: '# MatchCraft report\n\nOverall alignment: 78/100',
      })
    } else if (path.endsWith('/analyses') && method === 'GET') {
      await route.fulfill({ json: deleted ? [] : [completed] })
    } else if (path.endsWith(`/analyses/${ready.id}`) && method === 'DELETE') {
      deleted = true
      await route.fulfill({ status: 204, body: '' })
    } else {
      await route.fulfill({
        status: 404,
        json: { error: { message: `Unmocked ${method} ${path}` } },
      })
    }
  })

  await page.goto('/analyses/new')
  await expectReadablePlaceholder(page.getByLabel('Résumé text'))
  await page.getByLabel('Résumé text').fill(resumeText)
  await page.getByRole('button', { name: 'Review résumé text' }).click()
  await expect(page.getByRole('heading', { name: 'Review the extraction' })).toBeVisible()
  await page.getByRole('button', { name: 'Confirm and continue' }).click()
  await page.getByLabel('Job description').fill(jobText)
  await page.getByRole('button', { name: 'Parse requirements' }).click()
  await expect(page.getByRole('heading', { name: 'Required' })).toBeVisible()
  await expect(page.locator('aside').getByText('Kubernetes', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Run analysis' }).click()

  await expect(page.getByLabel('78 out of 100')).toBeVisible()
  await expect(page.getByText('Matched (1)')).toBeVisible()
  await expect(page.getByText('Unsupported (1)')).toBeVisible()
  await expect(
    page.getByText('Built Python services that processed 2 million records each week.'),
  ).toBeVisible()

  await page.getByRole('link', { name: /Open bullet workshop/i }).click()
  await page.getByRole('button', { name: 'Switch to dark theme' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  const selectedBullet = page.getByRole('button', {
    name: /Built Python services that processed 2 million records each week/,
  })
  await expect(selectedBullet).toHaveClass(/dark:bg-moss-950/)
  await expect(selectedBullet.locator('span')).toHaveClass(/text-stone-600/)
  await expectReadableText(selectedBullet)
  await expectReadableText(selectedBullet.locator('span'))
  await expectReadableText(page.getByText('Local-first by design'))
  await expectReadableText(
    page.getByText(
      'Your documents stay on this machine unless you configure a remote model endpoint.',
    ),
  )
  await expectReadableText(
    page.getByText(
      'A rewrite, its factual source, rationale, and confirmation marker will appear here.',
    ),
  )
  const rewriteButton = page.getByRole('button', { name: 'Generate safe rewrite' })
  await expectReadableText(rewriteButton)
  await rewriteButton.click()
  await expect(page.getByText(/insert verified outcome/i)).toBeVisible()
  await expect(page.getByText('confirmation required', { exact: true })).toBeVisible()

  await page.getByRole('link', { name: 'Results' }).click()
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Markdown' }).click(),
  ])
  // The client names the blob from the analysis id; a cross-origin href would have
  // ignored the download attribute and navigated away from the application.
  expect(download.suggestedFilename()).toMatch(/^matchcraft-.+\.md$/)

  await page.getByRole('link', { name: 'Analysis history' }).click()
  await page.getByRole('button', { name: /Delete Senior Software Engineer/i }).click()
  await expect(page.getByRole('dialog')).toContainText('Delete this analysis?')
  await page.getByRole('button', { name: 'Delete permanently' }).click()
  await expect(page.getByRole('heading', { name: 'Nothing saved yet' })).toBeVisible()
  // Deleting removes the button that had focus. Without an explicit restore, focus
  // falls to <body> and the next Tab restarts from the top of the document, with no
  // announcement that anything happened (WCAG 2.4.3 and 4.1.3).
  await expect(page.getByRole('status')).toContainText(/Deleted Senior Software Engineer/i)
  await expect.poll(() => page.evaluate(() => document.activeElement?.tagName ?? '')).toBe('H1')
  await page
    .getByRole('navigation', { name: 'Primary' })
    .getByRole('link', { name: 'New analysis' })
    .click()
  await expectReadablePlaceholder(page.getByLabel('Résumé text'))
})
