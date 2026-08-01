import {
  UserManager,
  WebStorageStateStore,
  type User,
} from "oidc-client-ts"
import {
  AUTH_AUTHORITY,
  AUTH_CLIENT_ID,
  AUTH_DISCOVERY_URL,
  AUTH_LOGOUT_REDIRECT_URI,
  AUTH_REDIRECT_URI,
  AUTH_SCOPE,
} from "./config"
import { fetchServerIdentity } from "./serverIdentity"
import type { AuthService, AuthUser } from "./types"


function createManager(): UserManager {
  if (!AUTH_AUTHORITY || !AUTH_CLIENT_ID) {
    throw new Error("OIDC auth requires VITE_AUTH_AUTHORITY and VITE_AUTH_CLIENT_ID.")
  }
  return new UserManager({
    authority: AUTH_AUTHORITY,
    metadataUrl: AUTH_DISCOVERY_URL || undefined,
    client_id: AUTH_CLIENT_ID,
    redirect_uri: AUTH_REDIRECT_URI,
    post_logout_redirect_uri: AUTH_LOGOUT_REDIRECT_URI,
    response_type: "code",
    scope: AUTH_SCOPE,
    silent_redirect_uri: AUTH_REDIRECT_URI,
    automaticSilentRenew: true,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
  })
}


export class OidcAuthService implements AuthService {
  readonly mode = "oidc" as const
  private readonly manager = createManager()

  private async currentUser(): Promise<User | null> {
    let user = await this.manager.getUser()
    if (user?.expired) {
      try {
        user = await this.manager.signinSilent()
      } catch {
        await this.manager.removeUser()
        return null
      }
    }
    return user
  }

  private async identityFor(user: User | null): Promise<AuthUser | null> {
    if (!user?.access_token || user.expired) {
      return null
    }
    return fetchServerIdentity({ Authorization: `Bearer ${user.access_token}` })
  }

  async boot(): Promise<AuthUser | null> {
    return this.identityFor(await this.currentUser())
  }

  async getAuthHeaders(): Promise<Record<string, string>> {
    const user = await this.currentUser()
    if (!user?.access_token) {
      return {}
    }
    return { Authorization: `Bearer ${user.access_token}` }
  }

  async login(): Promise<AuthUser | null> {
    await this.manager.signinRedirect()
    return null
  }

  async logout(): Promise<void> {
    const user = await this.manager.getUser()
    if (user) {
      await this.manager.signoutRedirect()
      return
    }
    await this.manager.removeUser()
  }

  async handleCallback(): Promise<AuthUser | null> {
    const user = await this.manager.signinCallback()
    return this.identityFor(user ?? await this.manager.getUser())
  }
}
