import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  title: string // tooltip + accessible label
  children: ReactNode
  danger?: boolean
}

export function IconButton({ title, danger, className = '', children, ...rest }: Props) {
  return (
    <button
      title={title}
      aria-label={title}
      className={`inline-flex cursor-pointer items-center justify-center rounded-sm border
        border-transparent p-1 transition-colors duration-150
        disabled:cursor-not-allowed disabled:opacity-40
        ${danger ? 'text-dim hover:bg-error/10 hover:text-error' : 'text-dim hover:bg-dim/10 hover:text-text'}
        ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
