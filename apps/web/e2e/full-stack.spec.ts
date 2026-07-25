import { readFile } from 'node:fs/promises'

import { expect, test } from '@playwright/test'

test('persists and deletes a real deterministic analysis through the browser', async ({ page }) => {
  const resumeText = `Jordan Rivera
jordan.rivera@example.test

EXPERIENCE
• Built Python services that processed 2 million records each week.
• Reduced validation failures by 32% with automated tests.

SKILLS
Python, FastAPI, SQL, React, TypeScript, Docker

EDUCATION
Bachelor of Science in Information Systems`
  const correctedResumeText = resumeText.replace(
    'processed 2 million records each week',
    'processed 2 million public records each week',
  )
  const jobText = `Senior Software Engineer
Company: Acme Public Systems

Required Qualifications
• Python and SQL are required.
• Experience with FastAPI and React is required.

Preferred Qualifications
• Kubernetes preferred.

Responsibilities
• Build reliable services and improve automated testing.`

  await page.goto('/analyses/new')
  await page.getByLabel('Résumé text').fill(resumeText)
  await page.getByRole('button', { name: 'Review résumé text' }).click()
  await expect(page.getByRole('heading', { name: 'Review the extraction' })).toBeVisible()
  await expect(page.getByLabel('Extracted résumé text')).toHaveValue(resumeText)
  await page.getByLabel('Extracted résumé text').fill(correctedResumeText)
  await page.getByRole('button', { name: 'Confirm and continue' }).click()

  await page.getByLabel('Job description').fill(jobText)
  await page.getByLabel('Add local AI insights when available').uncheck()
  await page.getByRole('button', { name: 'Parse requirements' }).click()
  await expect(page.getByRole('heading', { name: 'Required' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Preferred' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Context & themes' })).toBeVisible()
  await expect(
    page.locator('aside').getByRole('listitem').filter({ hasText: 'Python' }),
  ).toBeVisible()
  await expect(
    page.locator('aside').getByRole('listitem').filter({ hasText: 'Kubernetes' }),
  ).toBeVisible()
  await expect(
    page
      .locator('aside')
      .getByRole('listitem')
      .filter({ hasText: 'Build reliable services and improve automated testing.' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Run analysis' }).click()

  await expect(page.locator('[aria-label$="out of 100"]')).toBeVisible()
  await expect(page.getByText('Required skill alignment')).toBeVisible()
  await expect(
    page
      .getByText('Built Python services that processed 2 million public records each week.')
      .first(),
  ).toBeVisible()
  await expect(page.getByText('No résumé evidence found.').first()).toBeVisible()

  await page.getByRole('link', { name: /Open bullet workshop/i }).click()
  await page.getByRole('button', { name: 'Generate safe rewrite' }).first().click()
  await expect(page.getByText(/insert verified outcome/i).first()).toBeVisible()
  await expect(page.getByText('confirmation required', { exact: true }).first()).toBeVisible()

  await page.getByRole('link', { name: 'Results' }).click()
  const [markdown] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Markdown' }).click(),
  ])
  expect(markdown.suggestedFilename()).toMatch(/^matchcraft-[a-f0-9-]+\.md$/)
  const markdownPath = await markdown.path()
  expect(markdownPath).not.toBeNull()
  const markdownText = await readFile(markdownPath, 'utf8')
  expect(markdownText).toContain('## Requirement evidence')
  expect(markdownText).toContain(
    'Built Python services that processed 2 million public records each week.',
  )
  expect(markdownText).toContain('### Kubernetes — not_found')
  expect(markdownText).toContain('Résumé evidence: None found')
  const [json] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'JSON' }).click(),
  ])
  expect(json.suggestedFilename()).toMatch(/^matchcraft-[a-f0-9-]+\.json$/)
  const jsonPath = await json.path()
  expect(jsonPath).not.toBeNull()
  const exported = JSON.parse(await readFile(jsonPath, 'utf8')) as {
    state: string
    model_status: string
    overall_score: number
    scores: Array<{ category: string; score: number; maximum: number }>
    evidence: Array<{ requirement: string; status: string; resume_excerpt: string | null }>
  }
  expect(exported.state).toBe('completed')
  expect(exported.model_status).toBe('skipped')
  expect(exported.scores).toHaveLength(8)
  // A category with no detected requirement is not scored: it carries a zero maximum and
  // is excluded, so the assessed total is at most 100 and the overall score is a
  // percentage of what was actually assessed rather than of a fixed denominator.
  const assessed = exported.scores.reduce((total, item) => total + item.maximum, 0)
  const earned = exported.scores.reduce((total, item) => total + item.score, 0)
  expect(assessed).toBeGreaterThan(0)
  expect(assessed).toBeLessThanOrEqual(100)
  expect(exported.scores.every((item) => item.score <= item.maximum)).toBe(true)
  expect(exported.overall_score).toBeCloseTo((earned / assessed) * 100, 0)
  const supportedPython = exported.evidence.find(
    (item) => item.requirement === 'Python' && item.status === 'supported',
  )
  expect(supportedPython?.resume_excerpt).toBeTruthy()
  expect(correctedResumeText).toContain(supportedPython!.resume_excerpt!)
  const missingKubernetes = exported.evidence.find((item) => item.requirement === 'Kubernetes')
  expect(missingKubernetes).toMatchObject({ status: 'not_found', resume_excerpt: null })

  await page.getByRole('link', { name: 'Analysis history' }).click()
  await expect(page.getByText('Senior Software Engineer — Acme Public Systems')).toBeVisible()
  await page
    .getByRole('button', { name: 'Rename Senior Software Engineer — Acme Public Systems' })
    .click()
  await page.getByLabel('Analysis name').fill('Release acceptance analysis')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Release acceptance analysis', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Open Release acceptance analysis' }).click()
  await expect(page.getByRole('heading', { name: 'Release acceptance analysis' })).toBeVisible()
  await page.getByRole('link', { name: 'Analysis history' }).click()
  await page.getByRole('button', { name: 'Delete Release acceptance analysis' }).click()
  await page.getByRole('button', { name: 'Delete permanently' }).click()
  await expect(page.getByRole('heading', { name: 'Nothing saved yet' })).toBeVisible()

  const storedAnalyses = await page.request.get('http://127.0.0.1:8001/api/v1/analyses')
  expect(storedAnalyses.ok()).toBe(true)
  expect(await storedAnalyses.json()).toEqual([])
})
