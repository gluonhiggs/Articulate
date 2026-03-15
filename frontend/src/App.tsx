import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { Home } from './pages/Home'
import { MockTest } from './pages/MockTest'
import { Part1Practice } from './pages/Part1Practice'
import { Part2Practice } from './pages/Part2Practice'
import { Part3Practice } from './pages/Part3Practice'
import { QuestionDetail } from './pages/QuestionDetail'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/practice/part1" element={<Part1Practice />} />
          <Route path="/practice/part2" element={<Part2Practice />} />
          <Route path="/practice/part3" element={<Part3Practice />} />
          <Route path="/practice/:questionId" element={<QuestionDetail />} />
          <Route path="/mock-test" element={<MockTest />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
