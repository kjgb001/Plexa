import {
  useEffect,
  useState,
  type ReactNode,
} from "react"
import { DevAuthService } from "./devAuth"
import type { AuthService, AuthStatus, AuthUser } from "./types"
import { AuthContext } from "./AuthContext"

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authService] = useState<AuthService>(() => new DevAuthService())
  const [status, setStatus] = useState<AuthStatus>("booting")
  const [user, setUser] = useState<AuthUser | null>(null)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let active = true

    async function boot() {
      try {
        const nextUser = await authService.boot()

        if (!active) {
          return
        }

        setUser(nextUser)
        setStatus(nextUser ? "authenticated" : "unauthenticated")
      } catch (err) {
        if (!active) {
          return
        }

        setError(err instanceof Error ? err : new Error("Auth boot failed"))
        setStatus("error")
      }
    }

    void boot()

    return () => {
      active = false
    }
  }, [authService])

  async function login(userId: string) {
    setError(null)
    const nextUser = await authService.login(userId)
    setUser(nextUser)
    setStatus("authenticated")
  }

  async function logout() {
    await authService.logout()
    setUser(null)
    setStatus("unauthenticated")
  }

  async function handleCallback() {
    setStatus("booting")
    setError(null)

    try {
      const nextUser = await authService.handleCallback()
      setUser(nextUser)
      setStatus(nextUser ? "authenticated" : "unauthenticated")
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Auth callback failed"))
      setStatus("error")
    }
  }

  return (
    <AuthContext.Provider
      value={{
        authService,
        status,
        user,
        error,
        login,
        logout,
        handleCallback,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
