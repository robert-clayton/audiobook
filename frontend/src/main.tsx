import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import '@fontsource-variable/jetbrains-mono'
import './index.css'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000,
      retry: 1,
      refetchIntervalInBackground: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          style: {
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border-strong)',
            borderRadius: '2px',
            color: 'var(--color-text)',
            fontFamily: 'var(--font-mono)',
            fontSize: '13px',
          },
        }}
      />
    </QueryClientProvider>
  </StrictMode>,
)
