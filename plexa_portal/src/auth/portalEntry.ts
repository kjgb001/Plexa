const STORAGE_KEY = "plexa_post_login_path"
const PORTAL_KEY = "plexa_active_portal"

export function rememberPostLoginPath(path: string): void {
  sessionStorage.setItem(STORAGE_KEY, path)
}

export function consumePostLoginPath(): string | null {
  const value = sessionStorage.getItem(STORAGE_KEY)
  sessionStorage.removeItem(STORAGE_KEY)
  return value
}

export function rememberPortalChoice(portal: "student" | "instructor"): void {
  sessionStorage.setItem(PORTAL_KEY, portal)
}

export function getRememberedPortalChoice(): "student" | "instructor" | null {
  const value = sessionStorage.getItem(PORTAL_KEY)
  if (value === "student" || value === "instructor") {
    return value
  }
  return null
}
