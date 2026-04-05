import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-background">
      {/* Backdrop - mobile only, shown when sidebar open */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-10 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - always visible on md+, slide-in on mobile */}
      <div className={`fixed inset-y-0 left-0 z-20 transition-transform duration-300
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0`}>
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main content - full width on mobile, offset on md+ */}
      <main className="flex-1 ml-0 md:ml-64 min-h-screen overflow-x-hidden pt-14 md:pt-0">
        {/* Hamburger button - mobile only */}
        <button
          className="md:hidden fixed top-4 left-4 z-30 p-2 rounded-lg bg-sidebar border border-cardBorder text-textSecondary hover:text-textPrimary"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open menu"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <Outlet />
      </main>
    </div>
  )
}
