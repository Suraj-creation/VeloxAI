import { ReactNode } from 'react'
import { SideNav } from '@/app/layout/SideNav'
import { StatusBar } from '@/app/layout/StatusBar'
import { TopNav } from '@/app/layout/TopNav'

type AppShellProps = {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-shell-sidebar">
        <SideNav />
      </aside>
      <div className="app-shell-main">
        <TopNav />
        <StatusBar />
        <main className="app-content">{children}</main>
      </div>
    </div>
  )
}
