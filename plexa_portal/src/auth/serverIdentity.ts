import { API_BASE_URL, TARGET_API_VERSION } from "../api/config"
import type { AuthUser } from "./types"


interface AuthMeResponse {
  user_id: string
  roles: string[]
  is_admin: boolean
  can_access_instructor_portal: boolean
  owned_course_ids: string[]
  instructed_course_ids: string[]
}


export async function fetchServerIdentity(
  headers: Record<string, string>,
): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/${TARGET_API_VERSION}/auth/me`, { headers })
  if (!response.ok) {
    throw new Error("The server rejected the authenticated identity.")
  }
  const identity = await response.json() as AuthMeResponse
  return {
    userId: identity.user_id,
    roles: identity.roles,
    isAdmin: identity.is_admin,
    canAccessInstructorPortal: identity.can_access_instructor_portal,
    ownedCourseIds: identity.owned_course_ids,
    instructedCourseIds: identity.instructed_course_ids,
  }
}
