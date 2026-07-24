import { Link } from 'react-router-dom'
import { EmptyState } from '../components/ui/EmptyState'

export function NotFound() {
  return (
    <div className="flex w-full flex-col items-center gap-3 py-12">
      <EmptyState>page not found</EmptyState>
      <Link to="/" className="text-[13px] text-accent hover:underline">
        back to dashboard
      </Link>
    </div>
  )
}
