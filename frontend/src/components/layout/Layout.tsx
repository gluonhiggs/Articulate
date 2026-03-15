import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

export function Layout() {
  return (
    <div className="flex min-h-screen bg-background">
      {/* Fixed sidebar */}
      <div className="fixed inset-y-0 left-0 z-20">
        <Sidebar />
      </div>

      {/* Main content offset by sidebar width */}
      <main className="flex-1 ml-64 min-h-screen overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  )
}
