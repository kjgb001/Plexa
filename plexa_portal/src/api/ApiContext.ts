import { createContext } from "react"
import type { CourseApi } from "./courses"
import type { InstructorApi } from "./instructor"
import type { SessionApi } from "./sessions"

export interface ApiContextValue {
  courseApi: CourseApi
  instructorApi: InstructorApi
  sessionApi: SessionApi
}

export const ApiContext = createContext<ApiContextValue | null>(null)
