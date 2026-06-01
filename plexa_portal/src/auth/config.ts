import type { AuthMode } from "./types"

export const AUTH_MODE = (import.meta.env.VITE_AUTH_MODE ?? "dev") as AuthMode
export const ENABLE_DEV_LOGIN =
  (import.meta.env.VITE_ENABLE_DEV_LOGIN ?? "false").trim().toLowerCase() === "true"
export const AUTH_AUTHORITY = import.meta.env.VITE_AUTH_AUTHORITY ?? ""
export const AUTH_DISCOVERY_URL = import.meta.env.VITE_AUTH_DISCOVERY_URL ?? ""
export const AUTH_CLIENT_ID = import.meta.env.VITE_AUTH_CLIENT_ID ?? ""
export const AUTH_SCOPE = import.meta.env.VITE_AUTH_SCOPE ?? "openid profile email"
export const AUTH_REDIRECT_URI =
  import.meta.env.VITE_AUTH_REDIRECT_URI ?? `${window.location.origin}/auth/callback`
export const AUTH_LOGOUT_REDIRECT_URI =
  import.meta.env.VITE_AUTH_LOGOUT_REDIRECT_URI ?? `${window.location.origin}/login`
export const AUTH_USER_ID_CLAIM = import.meta.env.VITE_AUTH_USER_ID_CLAIM ?? "sub"
