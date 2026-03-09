export class DevAuthService {
  async getAuthHeaders(): Promise<Record<string, string>> {
    const user = localStorage.getItem("plexa_user")

    if (!user) {
      return {}
    }

    return {
      "X-User-Id": user
    }
  }

  login(userId: string) {
    localStorage.setItem("plexa_user", userId)
  }

  logout() {
    localStorage.removeItem("plexa_user")
  }
}