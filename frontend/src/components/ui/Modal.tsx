import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import { IconButton } from './IconButton'

interface Props {
  open: boolean
  onClose: () => void
  title: ReactNode
  /** Extra header content, right-aligned before the close button. */
  headerExtra?: ReactNode
  children: ReactNode
  footer?: ReactNode
  maxWidth?: string // tailwind max-w-* class
  tall?: boolean // fixed 85vh body (diff / editor dialogs)
  /** Return false to veto closing (unsaved-changes guard). */
  onBeforeClose?: () => boolean
}

export function Modal({
  open,
  onClose,
  title,
  headerExtra,
  children,
  footer,
  maxWidth = 'max-w-3xl',
  tall,
  onBeforeClose,
}: Props) {
  const closeRef = useRef<() => void>(onClose)
  closeRef.current = () => {
    if (onBeforeClose && !onBeforeClose()) return
    onClose()
  }

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        closeRef.current()
      }
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) closeRef.current()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={`flex w-full ${maxWidth} flex-col rounded-sm border border-border-strong
          bg-surface ${tall ? 'h-[85vh]' : 'max-h-[85vh]'}`}
        style={{ animation: 'dialog-rise 150ms ease-out' }}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-3">
          <h2 className="truncate text-[15px] font-bold text-text">{title}</h2>
          <div className="flex shrink-0 items-center gap-3">
            {headerExtra}
            <IconButton title="Close" onClick={() => closeRef.current()}>
              <X size={16} />
            </IconButton>
          </div>
        </div>
        <div className="flex min-h-0 flex-grow flex-col overflow-y-auto p-4">{children}</div>
        {footer && (
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border px-4 py-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
