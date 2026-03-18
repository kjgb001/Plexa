import { createContext } from "react"
import type { AuthService, AuthStatus, AuthUser } from "./types"

export interface AuthContextValue {
  authService: AuthService
  status: AuthStatus
  user: AuthUser | null
  error: Error | null
  login(userId: string): Promise<void>
  logout(): Promise<void>
  handleCallback(): Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
