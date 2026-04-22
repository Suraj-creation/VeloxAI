import { ReactNode } from 'react'

type ThemeProviderProps = {
  children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  return <div className="theme-root">{children}</div>
}
