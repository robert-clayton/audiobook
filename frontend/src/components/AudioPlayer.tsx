/** Native audio element, restyled minimally to sit in the industrial theme. */
export function AudioPlayer({ src, className = '' }: { src: string; className?: string }) {
  return (
    <audio
      controls
      preload="none"
      src={src}
      className={`h-9 rounded-sm ${className}`}
      style={{ colorScheme: 'dark', accentColor: 'var(--color-accent)' }}
    />
  )
}
