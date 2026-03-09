import { HttpClient } from "./http"
import { CourseApi } from "./courses"
import { SessionApi } from "./sessions"
import { DevAuthService } from "../auth/devAuth"

const auth = new DevAuthService()
const http = new HttpClient(() => auth.getAuthHeaders())

export const courseApi = new CourseApi(http)
export const sessionApi = new SessionApi(http)
export const authService = auth