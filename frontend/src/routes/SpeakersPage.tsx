import { useQuery } from '@tanstack/react-query'
import { FileText } from 'lucide-react'
import { useState } from 'react'
import { getSpeakers } from '../api/endpoints'
import { seg } from '../api/client'
import { AudioPlayer } from '../components/AudioPlayer'
import { PageHeader } from '../components/PageHeader'
import { TranscriptDialog } from '../components/dialogs/TranscriptDialog'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import { IconButton } from '../components/ui/IconButton'
import { Skeleton } from '../components/ui/Skeleton'
import { qk } from '../lib/queryKeys'

export function SpeakersPage() {
  const [editing, setEditing] = useState<string | null>(null)
  const { data, isLoading } = useQuery({ queryKey: qk.speakers, queryFn: getSpeakers })

  return (
    <>
      <PageHeader
        title="Speakers"
        backTo="/"
        extra={
          <span className="hidden text-[11px] text-dim sm:inline">
            reference voices for cloning — missing transcript falls back to x-vector-only
          </span>
        }
      />

      {isLoading && (
        <div className="flex w-full flex-col gap-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      )}

      {data && data.length === 0 && <EmptyState>no speakers found in speakers/</EmptyState>}

      <div className="flex w-full flex-col gap-2">
        {data?.map((sp) => (
          <div
            key={sp.name}
            className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 rounded-sm border
              border-border bg-surface px-4 py-2.5"
          >
            <div className="flex w-52 shrink-0 flex-col">
              <span className="truncate text-[13px] font-medium text-text">{sp.name}</span>
              <span className="text-[11px] text-dim">
                {sp.duration_s != null ? `${sp.duration_s.toFixed(1)}s` : '?'}
              </span>
            </div>
            {sp.has_transcript ? (
              <Badge color="var(--color-success)">transcript</Badge>
            ) : (
              <Badge color="var(--color-warning)">no transcript</Badge>
            )}
            <span className="min-w-0 flex-grow truncate text-[11px] text-dim">
              {sp.used_by.length ? sp.used_by.join(', ') : 'unused'}
            </span>
            <AudioPlayer src={`/api/speaker_audio/${seg(sp.name)}`} className="w-64 shrink-0" />
            <IconButton title="View / edit transcript" onClick={() => setEditing(sp.name)}>
              <FileText size={15} />
            </IconButton>
          </div>
        ))}
      </div>

      <TranscriptDialog speaker={editing} onClose={() => setEditing(null)} />
    </>
  )
}
