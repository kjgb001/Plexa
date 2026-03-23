import { createContext } from "react"
import type { ThemeMode } from "./types"

export interface ThemeContextValue {
  theme: ThemeMode
  toggleTheme(): void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
