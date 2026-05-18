import { createContext } from "react"
import type { AuthMode, AuthService, AuthStatus, AuthUser } from "./types"

export interface AuthContextValue {
  mode: AuthMode
  authService: AuthService
  status: AuthStatus
  user: AuthUser | null
  error: Error | null
  login(userId?: string): Promise<void>
  logout(): Promise<void>
  handleCallback(): Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
