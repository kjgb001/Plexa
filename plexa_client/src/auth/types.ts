export type AuthStatus =
  | "booting"
  | "authenticated"
  | "unauthenticated"
  | "error"

export interface AuthUser {
  userId: string
}

export interface AuthService {
  boot(): Promise<AuthUser | null>
  getAuthHeaders(): Promise<Record<string, string>>
  login(userId: string): Promise<AuthUser>
  logout(): Promise<void>
  handleCallback(): Promise<AuthUser | null>
}
