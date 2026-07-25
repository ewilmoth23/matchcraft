import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from '../layouts/AppLayout'
import { LoadingState } from '../components/Status'

const BulletWorkshopPage = lazy(() =>
  import('../pages/BulletWorkshopPage').then((module) => ({ default: module.BulletWorkshopPage })),
)
const DashboardPage = lazy(() =>
  import('../pages/DashboardPage').then((module) => ({ default: module.DashboardPage })),
)
const HistoryPage = lazy(() =>
  import('../pages/HistoryPage').then((module) => ({ default: module.HistoryPage })),
)
const InterviewPage = lazy(() =>
  import('../pages/InterviewPage').then((module) => ({ default: module.InterviewPage })),
)
const JobReviewPage = lazy(() =>
  import('../pages/JobReviewPage').then((module) => ({ default: module.JobReviewPage })),
)
const NewAnalysisPage = lazy(() =>
  import('../pages/NewAnalysisPage').then((module) => ({ default: module.NewAnalysisPage })),
)
const ResultsPage = lazy(() =>
  import('../pages/ResultsPage').then((module) => ({ default: module.ResultsPage })),
)
const ResumeReviewPage = lazy(() =>
  import('../pages/ResumeReviewPage').then((module) => ({ default: module.ResumeReviewPage })),
)
const SettingsPage = lazy(() =>
  import('../pages/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)

export function App() {
  return (
    <Suspense
      fallback={
        <div className="p-8">
          <LoadingState label="Loading workspace" />
        </div>
      }
    >
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="analyses/new" element={<NewAnalysisPage />} />
          <Route path="resumes/:resumeId/review" element={<ResumeReviewPage />} />
          <Route path="jobs/review" element={<JobReviewPage />} />
          <Route path="analyses/:analysisId" element={<ResultsPage />} />
          <Route path="analyses/:analysisId/bullets" element={<BulletWorkshopPage />} />
          <Route path="analyses/:analysisId/interview" element={<InterviewPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
