import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'
import { createLogger, errorData } from './lib/log'

const log = createLogger('app')

window.addEventListener('unhandledrejection', (event) => {
  log.error('unhandled promise rejection', errorData(event.reason))
})

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => log.error(`query ${JSON.stringify(query.queryKey)} failed`, errorData(error)),
  }),
  mutationCache: new MutationCache({
    onError: (error) => log.error('mutation failed', errorData(error)),
  }),
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,
      retry: 1,
      networkMode: 'always',
      refetchOnWindowFocus: false,
    },
  },
})

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('Root element not found')

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
