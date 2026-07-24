import { useParams } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { EmptyState } from '../components/ui/EmptyState'

export function SeriesPage() {
  const { name = '' } = useParams()
  return (
    <>
      <PageHeader title={name} backTo="/" />
      <EmptyState>series page — under construction</EmptyState>
    </>
  )
}
