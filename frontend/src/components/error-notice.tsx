import { useEffect, useRef, type ReactNode } from 'react'

export function ErrorNotice({ message, children }: { message: string; children?: ReactNode }) {
  const notice = useRef<HTMLDivElement>(null)
  useEffect(() => { if (message) notice.current?.focus() }, [message])
  if (!message) return null
  return <div ref={notice} tabIndex={-1} className="form-error" role="alert"><strong>Something needs your attention</strong><p>{message}</p>{children}</div>
}
