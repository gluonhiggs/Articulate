import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/layout/Layout'
import { Forecast } from './pages/Forecast'
import { Home } from './pages/Home'
import { InterviewHome } from './pages/interview/InterviewHome'
import { CandidateCv } from './pages/interview/CandidateCv'
import { InterviewPackOverview } from './pages/interview/InterviewPackOverview'
import { InterviewPractice } from './pages/interview/InterviewPractice'
import { PackStudio } from './pages/interview/PackStudio'
import { MockTest } from './pages/MockTest'
import { Part1Practice } from './pages/Part1Practice'
import { Part2Practice } from './pages/Part2Practice'
import { Part3Practice } from './pages/Part3Practice'
import { QuestionDetail } from './pages/QuestionDetail'

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/practice/part1" element={<Part1Practice />} />
            <Route path="/practice/part2" element={<Part2Practice />} />
            <Route path="/practice/part3" element={<Part3Practice />} />
            <Route path="/practice/part1/questions/:questionId" element={<QuestionDetail />} />
            <Route path="/practice/part2/questions/:questionId" element={<QuestionDetail />} />
            <Route path="/practice/part3/questions/:questionId" element={<QuestionDetail />} />
            <Route path="/mock-test" element={<MockTest />} />
            <Route path="/forecast" element={<Forecast />} />
            <Route path="/interview" element={<InterviewHome />} />
            <Route path="/interview/cv" element={<CandidateCv />} />
        <Route path="/interview/packs/:packId" element={<InterviewPackOverview />} />
            <Route path="/interview/packs/:packId/studio" element={<PackStudio />} />
            <Route path="/interview/questions/:questionId" element={<InterviewPractice />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  )
}
