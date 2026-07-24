import { PageHeader } from '../components/PageHeader'
import { EmptyState } from '../components/ui/EmptyState'

export function FailedPage() {
  return (
    <>
      <PageHeader title="Failed Chapters" titleColor="var(--color-error)" backTo="/" />
      <EmptyState>failed page — under construction</EmptyState>
    </>
  )
}
