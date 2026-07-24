import { createBrowserRouter, Outlet, RouterProvider } from 'react-router-dom'
import { useJobNotifications, useStatus } from './hooks/useStatusPoll'
import { DashboardPage } from './routes/DashboardPage'
import { FailedPage } from './routes/FailedPage'
import { NotFound } from './routes/NotFound'
import { SeriesPage } from './routes/SeriesPage'
import { SpeakersPage } from './routes/SpeakersPage'

function AppShell() {
  // Single mount point for the 2s status poll + job-completion notifications.
  const status = useStatus()
  useJobNotifications(status)

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 p-4">
      <Outlet />
    </div>
  )
}

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/series/:name', element: <SeriesPage /> },
      { path: '/failed', element: <FailedPage /> },
      { path: '/speakers', element: <SpeakersPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
