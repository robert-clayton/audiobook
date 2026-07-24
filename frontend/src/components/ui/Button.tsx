import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'accent' | 'dim' | 'success' | 'danger' | 'ghost'

const styles: Record<Variant, string> = {
  accent: 'border border-accent text-accent hover:bg-accent/10',
  dim: 'border border-dim/60 text-dim hover:border-dim hover:text-text hover:bg-dim/10',
  success: 'border border-success text-success hover:bg-success/10',
  danger: 'border border-error text-error hover:bg-error/10',
  ghost: 'border border-transparent text-dim hover:text-text hover:bg-dim/10',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  children: ReactNode
}

export function Button({ variant = 'dim', className = '', children, ...rest }: Props) {
  return (
    <button
      className={`inline-flex cursor-pointer items-center gap-1.5 rounded-sm bg-transparent
        px-3 py-1.5 text-xs font-medium tracking-wide uppercase transition-colors
        duration-150 disabled:cursor-not-allowed disabled:opacity-40
        ${styles[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
