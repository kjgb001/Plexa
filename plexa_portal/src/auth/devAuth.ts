import type { AuthService, AuthUser } from "./types"
import { fetchServerIdentity } from "./serverIdentity"

export class DevAuthService implements AuthService {
  readonly mode = "dev" as const

  async boot(): Promise<AuthUser | null> {
    const user = localStorage.getItem("plexa_user")

    if (!user) {
      return null
    }

    return fetchServerIdentity({ "X-User-Id": user })
  }

  async getAuthHeaders(): Promise<Record<string, string>> {
    const user = localStorage.getItem("plexa_user")

    if (!user) {
      return {}
    }

    return {
      "X-User-Id": user
    }
  }

  async login(userId?: string): Promise<AuthUser> {
    if (!userId?.trim()) {
      throw new Error("Dev auth login requires a user id.")
    }
    localStorage.setItem("plexa_user", userId)
    return fetchServerIdentity({ "X-User-Id": userId })
  }

  async logout(): Promise<void> {
    localStorage.removeItem("plexa_user")
  }

  async handleCallback(): Promise<AuthUser | null> {
    return this.boot()
  }
}
