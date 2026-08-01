export type AuthMode =
  | "dev"
  | "oidc"

export type AuthStatus =
  | "booting"
  | "authenticated"
  | "unauthenticated"
  | "error"

export interface AuthUser {
  userId: string
  displayName?: string | null
  roles: string[]
  isAdmin: boolean
  canAccessInstructorPortal: boolean
  ownedCourseIds: string[]
  instructedCourseIds: string[]
}

export interface AuthService {
  readonly mode: AuthMode
  boot(): Promise<AuthUser | null>
  getAuthHeaders(): Promise<Record<string, string>>
  login(userId?: string): Promise<AuthUser | null>
  logout(): Promise<void>
  handleCallback(): Promise<AuthUser | null>
}
