import type { ReactNode, RefObject } from 'react'

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  headingRef,
}: {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
  /** Lets a page move focus back to the heading after a destructive action. */
  headingRef?: RefObject<HTMLHeadingElement | null>
}) {
  return (
    <header className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div className="max-w-3xl">
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        {/* Analysis names accept up to 200 characters and used to overflow the header. */}
        <h1
          ref={headingRef}
          tabIndex={-1}
          className="break-words font-display text-3xl font-bold tracking-tight text-stone-950 outline-none dark:text-white sm:text-4xl"
        >
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-600 dark:text-stone-300 sm:text-base">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  )
}
