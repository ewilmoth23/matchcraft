import {
  Archive,
  Gauge,
  History,
  Menu,
  Moon,
  Plus,
  Settings,
  ShieldCheck,
  Sun,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

const navigation = [
  { to: '/', label: 'Dashboard', icon: Gauge },
  { to: '/analyses/new', label: 'New analysis', icon: Plus },
  { to: '/history', label: 'Analysis history', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function Brand() {
  return (
    <NavLink to="/" className="flex items-center gap-3 rounded-lg">
      <span className="grid size-10 place-items-center rounded-xl bg-moss-700 text-white shadow-sm dark:bg-moss-500 dark:text-stone-950">
        <Archive className="size-5" aria-hidden="true" />
      </span>
      <span>
        <span className="block font-display text-lg font-bold tracking-tight">MatchCraft</span>
        <span className="block text-[11px] font-medium text-stone-500 dark:text-stone-400">
          Evidence over guesswork
        </span>
      </span>
    </NavLink>
  )
}

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [dark, setDark] = useState(() => localStorage.getItem('matchcraft-theme') === 'dark')
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('matchcraft-theme', dark ? 'dark' : 'light')
  }, [dark])

  // Move focus into the drawer when it opens and return it to the trigger on close.
  // The wasOpen guard matters: without it the "restore" branch runs on first mount and
  // steals focus past the skip link on every page load.
  const wasOpen = useRef(false)
  useEffect(() => {
    if (mobileOpen) closeButtonRef.current?.focus()
    else if (wasOpen.current) menuButtonRef.current?.focus({ preventScroll: true })
    wasOpen.current = mobileOpen
  }, [mobileOpen])

  const nav = (
    <>
      <div className="px-3 py-2">
        <Brand />
      </div>
      <nav aria-label="Primary" className="mt-8 space-y-1">
        {navigation.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-moss-100 text-moss-900 dark:bg-moss-900 dark:text-moss-100'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-950 dark:text-stone-300 dark:hover:bg-stone-800 dark:hover:text-white'
              }`
            }
          >
            <Icon className="size-[18px]" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  )

  return (
    <div className="min-h-screen text-stone-900 dark:text-stone-100">
      <aside
        aria-label="Sidebar"
        className="fixed inset-y-0 left-0 hidden w-64 border-r border-stone-200/80 bg-stone-50/90 p-4 backdrop-blur dark:border-stone-800 dark:bg-stone-950/90 lg:flex lg:flex-col"
      >
        {nav}
        <div className="mt-auto rounded-xl border border-moss-200 bg-moss-50 p-3 dark:border-moss-900 dark:bg-moss-950">
          <div className="flex items-center gap-2 text-xs font-semibold text-moss-800 dark:text-moss-200">
            <ShieldCheck className="size-4" aria-hidden="true" /> Local-first by design
          </div>
          <p className="mt-1.5 text-xs leading-5 text-moss-700 dark:text-moss-300">
            Your documents stay on this machine unless you configure a remote model endpoint.
          </p>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-stone-950/40 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        >
          {/*
            A drawer with no dialog role, no focus move, and no Escape handler let a
            keyboard user tab straight past it into the page behind.
          */}
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="h-full w-72 bg-white p-4 shadow-xl dark:bg-stone-950"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setMobileOpen(false)
            }}
          >
            <div className="flex justify-end">
              <button
                type="button"
                ref={closeButtonRef}
                className="rounded-lg p-2"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation"
              >
                <X className="size-5" aria-hidden="true" />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      )}

      {/* inert keeps the background out of the tab order while the drawer is open. */}
      <div className="lg:pl-64" inert={mobileOpen}>
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-stone-200/70 bg-[#f7f8f5]/85 px-4 backdrop-blur-xl dark:border-stone-800 dark:bg-stone-950/85 sm:px-8">
          <button
            type="button"
            ref={menuButtonRef}
            className="rounded-lg p-2 lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-expanded={mobileOpen}
            aria-label="Open navigation"
          >
            <Menu className="size-5" aria-hidden="true" />
          </button>
          <p className="hidden text-xs font-medium text-stone-500 dark:text-stone-400 sm:block">
            Private workspace · single-user local mode
          </p>
          <button
            className="ml-auto rounded-lg border border-stone-200 bg-white p-2 text-stone-600 hover:text-stone-950 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300 dark:hover:text-white"
            onClick={() => setDark((value) => !value)}
            aria-label={`Switch to ${dark ? 'light' : 'dark'} theme`}
          >
            {dark ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
          </button>
        </header>
        {/* tabIndex is required for the skip link to actually move focus in Safari. */}
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-[1440px] px-4 py-8 outline-none sm:px-8 lg:px-10 lg:py-10"
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
