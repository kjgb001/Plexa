import { createContext } from "react"
import type { CourseApi } from "./courses"
import type { SessionApi } from "./sessions"

export interface ApiContextValue {
  courseApi: CourseApi
  sessionApi: SessionApi
}

export const ApiContext = createContext<ApiContextValue | null>(null)
