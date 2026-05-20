import {
  AUTH_AUTHORITY,
  AUTH_CLIENT_ID,
  AUTH_DISCOVERY_URL,
  AUTH_LOGOUT_REDIRECT_URI,
  AUTH_MODE,
  AUTH_REDIRECT_URI,
  AUTH_SCOPE,
  AUTH_USER_ID_CLAIM,
} from "./config"
import type { AuthService, AuthUser } from "./types"

const STORAGE_KEY = "plexa_oidc_session"
const PENDING_KEY = "plexa_oidc_pending"

interface DiscoveryDocument {
  authorization_endpoint: string
  token_endpoint: string
  end_session_endpoint?: string
}

interface StoredSession {
  accessToken: string
  idToken?: string
  expiresAt?: number
}

interface PendingLogin {
  state: string
  codeVerifier: string
}

function b64urlEncode(bytes: Uint8Array): string {
  const binary = Array.from(bytes, byte => String.fromCharCode(byte)).join("")
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "")
}

function randomString(length = 32): string {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  return b64urlEncode(bytes)
}

async function sha256(value: string): Promise<string> {
  const data = new TextEncoder().encode(value)
  const digest = await crypto.subtle.digest("SHA-256", data)
  return b64urlEncode(new Uint8Array(digest))
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".")
  if (parts.length !== 3) {
    return null
  }

  try {
    const segment = parts[1].replace(/-/g, "+").replace(/_/g, "/")
    const decoded = atob(segment + "=".repeat((4 - (segment.length % 4)) % 4))
    return JSON.parse(decoded) as Record<string, unknown>
  } catch {
    return null
  }
}

function readStoredSession(): StoredSession | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as StoredSession
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return null
  }
}

function writeStoredSession(session: StoredSession): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

function clearStoredSession(): void {
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem(PENDING_KEY)
}

function readPendingLogin(): PendingLogin | null {
  const raw = localStorage.getItem(PENDING_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as PendingLogin
  } catch {
    localStorage.removeItem(PENDING_KEY)
    return null
  }
}

function writePendingLogin(pending: PendingLogin): void {
  localStorage.setItem(PENDING_KEY, JSON.stringify(pending))
}

async function fetchDiscoveryDocument(): Promise<DiscoveryDocument> {
  const discoveryUrl = AUTH_DISCOVERY_URL || `${AUTH_AUTHORITY.replace(/\/$/, "")}/.well-known/openid-configuration`
  if (!discoveryUrl) {
    throw new Error("OIDC auth requires VITE_AUTH_AUTHORITY or VITE_AUTH_DISCOVERY_URL.")
  }

  const response = await fetch(discoveryUrl)
  if (!response.ok) {
    throw new Error("Failed to load OIDC discovery document.")
  }

  const document = await response.json() as DiscoveryDocument
  if (!document.authorization_endpoint || !document.token_endpoint) {
    throw new Error("OIDC discovery document is missing required endpoints.")
  }

  return document
}

function userFromSession(session: StoredSession): AuthUser | null {
  const sourceToken = session.idToken ?? session.accessToken
  const payload = decodeJwtPayload(sourceToken)
  if (!payload) {
    return null
  }

  const rawUserId = payload[AUTH_USER_ID_CLAIM]
  if (typeof rawUserId !== "string" || !rawUserId.trim()) {
    return null
  }

  const displayName =
    (typeof payload.name === "string" && payload.name)
    || (typeof payload.preferred_username === "string" && payload.preferred_username)
    || null

  return {
    userId: rawUserId,
    displayName,
  }
}

export class OidcAuthService implements AuthService {
  readonly mode = AUTH_MODE

  async boot(): Promise<AuthUser | null> {
    const session = readStoredSession()
    if (!session) {
      return null
    }

    if (session.expiresAt && Date.now() >= session.expiresAt) {
      clearStoredSession()
      return null
    }

    return userFromSession(session)
  }

  async getAuthHeaders(): Promise<Record<string, string>> {
    const session = readStoredSession()
    if (!session?.accessToken) {
      return {}
    }

    return {
      Authorization: `Bearer ${session.accessToken}`,
    }
  }

  async login(): Promise<AuthUser | null> {
    if (!AUTH_CLIENT_ID) {
      throw new Error("OIDC auth requires VITE_AUTH_CLIENT_ID.")
    }

    const discovery = await fetchDiscoveryDocument()
    const state = randomString()
    const codeVerifier = randomString(48)
    const codeChallenge = await sha256(codeVerifier)
    writePendingLogin({ state, codeVerifier })

    const url = new URL(discovery.authorization_endpoint)
    url.searchParams.set("client_id", AUTH_CLIENT_ID)
    url.searchParams.set("redirect_uri", AUTH_REDIRECT_URI)
    url.searchParams.set("response_type", "code")
    url.searchParams.set("scope", AUTH_SCOPE)
    url.searchParams.set("state", state)
    url.searchParams.set("code_challenge", codeChallenge)
    url.searchParams.set("code_challenge_method", "S256")

    window.location.assign(url.toString())
    return null
  }

  async logout(): Promise<void> {
    const discovery = await fetchDiscoveryDocument().catch(() => null)
    const session = readStoredSession()
    clearStoredSession()

    if (discovery?.end_session_endpoint) {
      const url = new URL(discovery.end_session_endpoint)
      url.searchParams.set("post_logout_redirect_uri", AUTH_LOGOUT_REDIRECT_URI)
      if (session?.idToken) {
        url.searchParams.set("id_token_hint", session.idToken)
      }
      window.location.assign(url.toString())
    }
  }

  async handleCallback(): Promise<AuthUser | null> {
    const params = new URLSearchParams(window.location.search)
    const code = params.get("code")
    const state = params.get("state")
    const error = params.get("error")
    if (error) {
      throw new Error(params.get("error_description") || error)
    }
    if (!code || !state) {
      return null
    }

    const pending = readPendingLogin()
    if (!pending || pending.state !== state) {
      throw new Error("OIDC state validation failed.")
    }

    const discovery = await fetchDiscoveryDocument()
    const body = new URLSearchParams({
      grant_type: "authorization_code",
      client_id: AUTH_CLIENT_ID,
      code,
      redirect_uri: AUTH_REDIRECT_URI,
      code_verifier: pending.codeVerifier,
    })
    const response = await fetch(discovery.token_endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body.toString(),
    })
    if (!response.ok) {
      throw new Error("OIDC token exchange failed.")
    }

    const payload = await response.json() as {
      access_token: string
      id_token?: string
      expires_in?: number
    }
    const session: StoredSession = {
      accessToken: payload.access_token,
      idToken: payload.id_token,
      expiresAt: typeof payload.expires_in === "number"
        ? Date.now() + (payload.expires_in * 1000)
        : undefined,
    }
    writeStoredSession(session)
    localStorage.removeItem(PENDING_KEY)

    window.history.replaceState(null, "", "/student/courses")
    return userFromSession(session)
  }
}
