import { createContext } from "react"
import type { AdminApi } from "./admin"
import type { CourseApi } from "./courses"
import type { InstructorApi } from "./instructor"
import type { SessionApi } from "./sessions"

export interface ApiContextValue {
  adminApi: AdminApi
  courseApi: CourseApi
  instructorApi: InstructorApi
  sessionApi: SessionApi
}

export const ApiContext = createContext<ApiContextValue | null>(null)
