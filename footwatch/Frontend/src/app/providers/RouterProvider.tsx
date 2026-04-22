import { BrowserRouter } from 'react-router-dom'
import { ReactNode } from 'react'

type RouterProviderProps = {
  children: ReactNode
}

export function RouterProvider({ children }: RouterProviderProps) {
  return <BrowserRouter>{children}</BrowserRouter>
}
