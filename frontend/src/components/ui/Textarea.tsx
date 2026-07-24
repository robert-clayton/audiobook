import type { TextareaHTMLAttributes } from 'react'

export function Textarea({
  className = '',
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`w-full resize-y rounded-sm border border-border bg-bg px-2.5 py-2
        font-mono text-[13px] leading-relaxed text-text placeholder:text-dim/60
        hover:border-border-strong focus:border-accent focus:outline-none ${className}`}
      {...rest}
    />
  )
}
