import type { ButtonHTMLAttributes } from 'react';
type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'quiet' | 'destructive'; pending?: boolean };
export function Button({ variant = 'primary', pending = false, className = '', children, disabled, ...props }: Props) {
  return <button {...props} disabled={disabled || pending} aria-busy={pending || undefined} className={`button button-${variant} ${className}`}>
    {pending && <span className="button-progress" aria-hidden="true"><i /><i /><i /></span>}{children}
  </button>;
}
