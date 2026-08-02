/** Portal authentication strategy selected at build time. */
export type AuthMode =
  | "dev"
  | "oidc"

/** Current state of the portal authentication bootstrap. */
export type AuthStatus =
  | "booting"
  | "authenticated"
  | "unauthenticated"
  | "error"

/** Server-authoritative identity and course-level portal permissions. */
export interface AuthUser {
  userId: string
  displayName?: string | null
  roles: string[]
  isAdmin: boolean
  canAccessInstructorPortal: boolean
  ownedCourseIds: string[]
  instructedCourseIds: string[]
}

/** Common lifecycle implemented by development and institutional auth clients. */
export interface AuthService {
  readonly mode: AuthMode
  /** Restore an existing identity during application startup. */
  boot(): Promise<AuthUser | null>
  /** Return headers required for an authenticated API request. */
  getAuthHeaders(): Promise<Record<string, string>>
  /** Start login or resolve a development identity. */
  login(userId?: string): Promise<AuthUser | null>
  /** End the local session and, when supported, the provider session. */
  logout(): Promise<void>
  /** Complete an institutional authorization callback. */
  handleCallback(): Promise<AuthUser | null>
}
